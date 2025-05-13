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

            source_db = source_client[db_name]
            source_collection = source_db[collection_name]

            dest_db = dest_client[db_name]
            dest_collection = dest_db[collection_name]

            # Check if the destination collection should be dropped
            if collection_config.drop_if_exists:
                dest_collection.drop()

            # Create the destination collection if it doesn't exist
            if not collection_name in dest_db.list_collection_names():
                dest_db.create_collection(collection_name)

            # Check if shard key should be created
            if collection_config.migrate_shard_key:
                source_shard_key = self._get_shard_key_ru(source_db, collection_config)
                if (source_shard_key is not None):
                    dest_client.admin.command(
                        "shardCollection",
                        f"{db_name}.{collection_name}",
                        key=source_shard_key)

            # Migrate indexes
            index_list = []
            source_indexes = source_collection.index_information()
            for source_index_name, source_index_info in source_indexes.items():
                index_keys = source_index_info['key']
                index_options = {k: v for k, v in source_index_info.items() if k not in ['key', 'v']}
                index_options['name'] = source_index_name
                index_list.append((index_keys, index_options))

            # TODO: Optimize compound indexes

            for index_keys, index_options in index_list:
                if self._is_ts_ttl_index(index_keys, index_options):
                    raise ValueError(f"Cannot migrate TTL index on _ts field for collection {collection_name}.")
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