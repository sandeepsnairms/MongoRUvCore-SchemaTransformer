import argparse
import json
import sys
from pymongo import MongoClient
from json_parser import JsonParser
from schema_migration import SchemaMigration
from entra_auth import create_entra_id_mongo_client

if __name__ == "__main__":
    # Take user input for URIs and configuration JSON file
    parser = argparse.ArgumentParser(description="MongoDB Schema Transformer")
    parser.add_argument("--source-uri", required=True, help="Source MongoDB URI")
    parser.add_argument("--dest-uri", required=True, help="Destination MongoDB URI")
    parser.add_argument("--config-file", required=True, help="Path to the configuration JSON file")
    parser.add_argument(
        "--mode",
        choices=["complete", "preIngestion", "postIngestion"],
        default="complete",
        help=(
            "Index migration mode. "
            "'complete' (default) creates all indexes. "
            "'preIngestion' creates only unique indexes (run before data ingestion). "
            "'postIngestion' creates only non-unique indexes and skips drop/create, "
            "colocation, and shard-key migration (run after data ingestion)."
        ),
    )
    parser.add_argument(
        "--blocking",
        action="store_true",
        help=(
            "(postIngestion only) Build indexes with blocking:true. "
            "WARNING: takes an exclusive lock on each collection during the "
            "build — writes to the target collection will fail and MUST be "
            "stopped before running."
        ),
    )
    parser.add_argument(
        "--dest-auth-entra-id",
        action="store_true",
        help=(
            "Authenticate to the destination Azure DocumentDB using "
            "Microsoft Entra ID via DefaultAzureCredential. The script must "
            "be run from an environment whose identity has been enabled and "
            "authorized on the destination Azure DocumentDB. When set, "
            "--dest-uri must be the Entra ID style connection string for the "
            "target cluster (no username / password embedded)."
        ),
    )
    args = parser.parse_args()

    source_uri = args.source_uri
    dest_uri = args.dest_uri
    config_file_path = args.config_file
    mode = args.mode
    blocking = args.blocking
    dest_auth_entra_id = args.dest_auth_entra_id

    if blocking and mode != "postIngestion":
        parser.error("--blocking can only be used with --mode postIngestion")

    print(f"\n{'=' * 70}")
    print(f"INDEX MIGRATION MODE: {mode.upper()}")
    print(f"{'=' * 70}")
    if mode == "preIngestion":
        print("Only UNIQUE indexes will be created. Run this BEFORE data ingestion.")
    elif mode == "postIngestion":
        print("Only NON-UNIQUE indexes will be created. Drop/create, colocation")
        print("and shard-key migration are SKIPPED. Run this AFTER data ingestion.")
    else:
        print("All indexes (unique and non-unique) will be created.")
    print(f"{'=' * 70}\n")

    if blocking:
        print("!" * 70)
        print("!!  WARNING: --blocking IS ENABLED")
        print("!!")
        print("!!  Indexes will be built with the createIndexes command using")
        print("!!  blocking: true. This takes an EXCLUSIVE LOCK on each target")
        print("!!  collection for the entire duration of the index build.")
        print("!!")
        print("!!  >>> ALL WRITES TO THE TARGET COLLECTIONS MUST BE STOPPED <<<")
        print("!!  >>> BEFORE PROCEEDING. Any writes issued during a blocking <<<")
        print("!!  >>> index build WILL FAIL.                                <<<")
        print("!!")
        print("!!  Stop application traffic, migration/ingestion jobs, and any")
        print("!!  other writers to the destination collections before continuing.")
        print("!" * 70)
        try:
            response = input("\nType 'yes' to confirm writes are stopped and continue: ").strip().lower()
        except EOFError:
            response = ""
        if response != "yes":
            print("Aborted. Blocking index build not started.")
            sys.exit(1)
        print()

    # Connect to the source and destination MongoDB instances
    source_client = MongoClient(source_uri)
    if dest_auth_entra_id:
        print("Destination auth: Microsoft Entra ID (DefaultAzureCredential).")
        dest_client = create_entra_id_mongo_client(dest_uri)
    else:
        print(
            "WARNING: Destination auth is using the connection string as-is. "
            "For production, prefer --dest-auth-entra-id to authenticate with "
            "the signed-in Microsoft Entra ID identity."
        )
        dest_client = MongoClient(dest_uri)

    # Load the configuration from the JSON file
    with open(config_file_path, 'r', encoding='utf-8') as config_file:
        json_config = json.load(config_file)

    # Parse the configuration into CollectionConfig objects
    parsed_collection_configs = JsonParser(json_config, source_client).parse_json()

    # Perform schema migration
    schema_migration = SchemaMigration(mode=mode, blocking=blocking)
    schema_migration.migrate_schema(source_client, dest_client, parsed_collection_configs)
