from typing import List, Tuple
from pymongo import MongoClient
from pymongo.database import Database
from collection_config import CollectionConfig

class SchemaMigration:
    """
    A class to handle schema migration tasks between MongoDB databases.

    This class provides functionality to migrate indexes and shard keys
    from source collections to destination collections. It ensures that
    the destination collections are properly created, and shard keys and
    indexes are replicated as needed.

    Methods:
        migrate_schema(source_client, dest_client, collection_configs):
            Migrates indexes and shard keys from source to destination collections.
    """

    def migrate_schema(
            self,
            source_client: MongoClient,
            dest_client: MongoClient,
            collection_configs: List[CollectionConfig]) -> None:
        """
        Migrate indexes and shard keys from source collections to destination collections.

        :param source_client: MongoDB client connected to the source database.
        :param dest_client: MongoDB client connected to the destination database.
        :param collection_configs: A list of CollectionConfig objects containing
                                   configuration details for each collection to migrate.
        """
        for collection_config in collection_configs:
            db_name = collection_config.db_name
            collection_name = collection_config.collection_name

            print(f"\nMigrating schema for collection: {db_name}.{collection_name}")

            source_db = source_client[db_name]
            source_collection = source_db[collection_name]

            dest_db = dest_client[db_name]
            dest_collection = dest_db[collection_name]

            # Check if the destination collection should be dropped
            if collection_config.drop_if_exists:
                print("-- Running drop command on target collection")
                dest_collection.drop()

            # Create the destination collection if it doesn't exist
            if not collection_name in dest_db.list_collection_names():
                print("-- Creating target collection")
                dest_db.create_collection(collection_name)
            else:
                print("-- Target collection already exists. Skipping creation.")

            # Check if shard key should be created
            if collection_config.migrate_shard_key:
                source_shard_key = self._get_shard_key_ru(source_db, collection_config)
                if (source_shard_key is not None):
                    print(f"-- Migrating shard key - {source_shard_key}.")
                    dest_client.admin.command(
                        "shardCollection",
                        f"{db_name}.{collection_name}",
                        key=source_shard_key)
                else:
                    print(f"-- No shard key found for collection {collection_name}. Skipping shard key setup.")
            else:
                print("-- Skipping shard key migration for collection")

            # Migrate indexes
            index_list = []
            source_indexes = source_collection.index_information()
            for source_index_name, source_index_info in source_indexes.items():
                index_keys = source_index_info['key']
                index_options = {k: v for k, v in source_index_info.items() if k not in ['key', 'v']}
                index_options['name'] = source_index_name
                index_list.append((index_keys, index_options))

            if collection_config.optimize_compound_indexes:
                print("-- Optimizing compound indexes if available")
                index_list = self._optimize_compound_indexes(index_list)

            print("-- Migrating indexes for collection")
            for index_keys, index_options in index_list:
                if self._is_ts_ttl_index(index_keys, index_options):
                    raise ValueError(f"Cannot migrate TTL index on _ts field for collection {collection_name}.")
                print(f"---- Creating index: {index_keys} with options: {index_options}")
                dest_collection.create_index(index_keys, **index_options)

    def _get_shard_key_ru(self, source_db: Database, collection_config: CollectionConfig):
        """
        Retrieve the shard key definition for a given collection.

        :param source_db: The source database object.
        :param collection_config: The configuration object for the collection.
        :return: The shard key.
        """
        get_collection_command = {}
        get_collection_command['customAction'] = 'GetCollection'
        get_collection_command['collection'] = collection_config.collection_name

        cosmos_collection = source_db.command(get_collection_command)
        if 'shardKeyDefinition' not in cosmos_collection:
            return None
        return cosmos_collection['shardKeyDefinition']

    def _is_ts_ttl_index(self, index_keys: List[Tuple], index_options: dict) -> bool:
        """
        Check if the given index is a TTL (Time-To-Live) index on _ts field.

        :param index: The index to check.
        :return: True if the index is a TTL index, False otherwise.
        """
        if 'expireAfterSeconds' in index_options and any('_ts' ==  index_key[0] for index_key in index_keys):
            return True
        return False

    def _optimize_compound_indexes(self, index_list: List[Tuple]) -> List[Tuple]:
        """
        Optimize compound indexes for the given collection configuration.
        """
        compound_indexes = []
        not_compound_indexes = []
        for index in index_list:
            keys, options = index
            if self._is_compound_index(index):
                compound_indexes.append(index)
            else:
                not_compound_indexes.append(index)

        # Sort compound indexes by the number of keys in descending order
        compound_indexes.sort(key=lambda x: len(x[0]), reverse=True)

        optimized_compound_indexes = []
        for compound_index in compound_indexes:
            keys, options = compound_index
            is_redundant = False
            for optimized_index in optimized_compound_indexes:
                optimized_keys, optimized_options = optimized_index
                if self._is_subarray(keys, optimized_keys):
                    is_redundant = True
                    break
            if not is_redundant:
                optimized_compound_indexes.append(compound_index)
        return optimized_compound_indexes + not_compound_indexes

    def _is_compound_index(self, index: Tuple) -> bool:
        """
        Check if the given index is a compound index.

        :param index: The index to check.
        :return: True if the index is compound, False otherwise.
        """
        not_compound_options = ['unique', 'sparse', 'expireAfterSeconds']
        keys, options = index
        if len(keys) > 1 and not any(opt in options for opt in not_compound_options):
            return True
        return False

    def _is_subarray(self, sub: List, main: List) -> bool:
        """
        Check if the list `sub` is an subarray of the list `main`.

        :param sub: The list to check as a subset.
        :param main: The list to check against.
        :return: True if `sub` is an subarray of `main`, False otherwise.
        """
        sub_len = len(sub)
        main_len = len(main)

        if sub_len > main_len:
            return False

        for i in range(main_len - sub_len + 1):
            if main[i:i + sub_len] == sub:
                return True
        return False
