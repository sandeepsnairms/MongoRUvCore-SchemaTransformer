import argparse
import json
from pymongo import MongoClient
from schema_migration import SchemaMigration
from collection_config import CollectionConfig

def parse_json(config, client):
    """
    Parse the JSON configuration file and return a list of CollectionConfig objects.

    :param config: The JSON configuration as a dictionary.
    :param source_client: MongoDB client connected to the source database.
    :return: A list of CollectionConfig objects.
    """
    collection_configs = {}

    for section in config.get("sections", []):
        include = section.get("include", [])
        exclude = section.get("exclude", [])
        include_collection_set = get_collections(include, client)
        exclude_collection_set = get_collections(exclude, client)

        collections_to_migrate = include_collection_set.difference(exclude_collection_set)

        migrate_shard_key = section.get("migrate_shard_key", "false").lower() == "true"
        drop_if_exists = section.get("drop_if_exists", "false").lower() == "true"
        optimize_compound_indexes = section.get("optimize_compound_indexes", "false").lower() == "true"

        for collection in collections_to_migrate:
            if collection in collection_configs:
                raise ValueError(f"Duplicate collection entry found: {collection}")

            db_name, collection_name = collection.split(".", 1)
            collection_config = CollectionConfig(
                db_name=db_name,
                collection_name=collection_name,
                migrate_shard_key=migrate_shard_key,
                drop_if_exists=drop_if_exists,
                optimize_compound_indexes=optimize_compound_indexes
            )
            collection_configs[collection] = collection_config
    return collection_configs.values()

def get_collections(collection_list, client):
    """
    Retrieve a set of fully qualified collection names based on the input list.

    :param collection_list: A list of collection patterns (e.g., "*", "db.*", "db.collection").
    :param client: MongoDB client connected to the source database.
    :return: A set of fully qualified collection names (e.g., "db.collection").
    """
    collection_set = set()
    for collection in collection_list:
        if collection == "*":
            # Include all collections in all databases
            for db_name in client.list_database_names():
                source_db = client[db_name]
                for collection_name in source_db.list_collection_names():
                    collection_set.add(f"{db_name}.{collection_name}")
        elif ".*" in collection:
            # Include all collections in a specific database
            db_name = collection.split(".*")[0]
            source_db = client[db_name]
            for collection_name in source_db.list_collection_names():
                collection_set.add(f"{db_name}.{collection_name}")
        else:
            # Include specific collections
            db_name, collection_name = collection.split(".", 1)
            source_db = client[db_name]
            if collection_name in source_db.list_collection_names():
                collection_set.add(f"{db_name}.{collection_name}")
    return collection_set

if __name__ == "__main__":
    # Take user input for URIs and configuration JSON file
    parser = argparse.ArgumentParser(description="MongoDB Schema Transformer")
    parser.add_argument("--source-uri", required=True, help="Source MongoDB URI")
    parser.add_argument("--dest-uri", required=True, help="Destination MongoDB URI")
    parser.add_argument("--config-file", required=True, help="Path to the configuration JSON file")
    args = parser.parse_args()

    source_uri = args.source_uri
    dest_uri = args.dest_uri
    config_file_path = args.config_file

    # Connect to the source and destination MongoDB instances
    source_client = MongoClient(source_uri)
    dest_client = MongoClient(dest_uri)

    # Load the configuration from the JSON file
    with open(config_file_path, 'r', encoding='utf-8') as config_file:
        json_config = json.load(config_file)

    # Parse the configuration into CollectionConfig objects
    parsed_collection_configs = parse_json(json_config, source_client)

    # Perform schema migration
    schema_migration = SchemaMigration()
    schema_migration.migrate_indexes(source_client, dest_client, parsed_collection_configs)
