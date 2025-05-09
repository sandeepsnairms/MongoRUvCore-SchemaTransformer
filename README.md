# Schema Transformer: Migrating RU-based Azure Cosmos DB for MongoDB to vCore-based

Schema Transformer is a Python script designed to analyze Mongo RU Collection schemas and efficiently transform them into a vCore-optimized structure. This ensures seamless compatibility and enhances query performance.

With this tool, you can generate index and sharding recommendations tailored specifically to your workload, making your migration smoother and more efficient.

## Supported Source and Target Versions

The tool supports the following versions:

- **Source:** Azure Cosmos DB for MongoDB RU-based (version 4.2 and above)
- **Target:** Azure Cosmos DB for MongoDB vCore (all versions)

## How to Run the Script

### Prerequisites

Before running the assessment, ensure that the client machine meets the following requirements:

- Access to both source and target MongoDB endpoints, either over a private or public network via the specified IP or hostname.
- Python (version 3.10 or above) must be installed.

### Steps to Run the Assessment

1. Download the latest release and unzip it.
2. Open the command prompt and navigate to the extracted directory.
3. Create a JSON file to define the collections to be migrated. Each section in the configuration will define the schema migration options for a set of collections (you can specify `*` to refer to all collections in an account and `db.*` to refer all collections within a database). Refer the next section for more details on configuration options. Here are some examples -

3.1. To specify all collections present in the account - 
    ```json
    {
        "sections": [
            {
                "include": [
                    "*"
                ],
                "exclude": [],
                "unsharded": "false",
                "drop_if_exists": "true",
                "optimize_compound_indexes": "true"
            }
        ]
    }
    ```
3.2. To specify all collections except a particular database
    ```json
    {
        "sections": [
            {
                "include": [
                    "*"
                ],
                "exclude": [
                    "db1.*"
                ],
                "unsharded": "false",
                "drop_if_exists": "true",
                "optimize_compound_indexes": "true"
            }
        ]
    }
    ```
3.3. To specify all collections except few
    ```json
    {
        "sections": [
            {
                "include": [
                    "*"
                ],
                "exclude": [
                    "db1.coll1",
                    "db2.coll2"
                ],
                "unsharded": "false",
                "drop_if_exists": "true",
                "optimize_compound_indexes": "true"
            }
        ]
    }
    ```
3.4. To migrate specific collections
    ```json
    {
        "sections": [
            {
                "include": [
                    "db1.coll1",
                    "db2.coll2"
                ],
                "unsharded": "false",
                "drop_if_exists": "true",
                "optimize_compound_indexes": "true"
            }
        ]
    }
    ```
3.5. To migrate different set of collections with different configuration options
    ```json
    {
        "sections": [
            {
                "include": [
                    "*"
                ],
                "exclude": [
                    "db1.coll1",
                    "db2.coll2"
                ],
                "unsharded": "false",
                "drop_if_exists": "true",
                "optimize_compound_indexes": "true"
            },
            {
                "include": [
                    "db1.coll1",
                    "db2.coll2"
                ],
                "unsharded": "false",
                "drop_if_exists": "true",
                "optimize_compound_indexes": "true"
            }
        ]
    }
    ```

4. Run the following command, providing the full path of the JSON file created in the previous step:

    ```cmd
    python main.py --config <path_to_your_json_file> --source-uri <source_mongo_uri> --dest-uri <destination_mongo_uri>
    ```

This process will generate a vCore-optimized schema with index and sharding recommendations based on your workload.


### Configuration options
1. migrate_shard_key: Set to `True` is existing shard key definition should be migrated. If set to `False` all collections getting created in target will not be sharded. Collections w/o a shard key definition is source will always remain unsharded in target irrespective of this option. Default: `False`.
2. drop_if_exists: Set to `True` if collections with same name in target have to be dropped and recreated. Default: `False`.
3. optimize_compound_indexes: Set to `True` if compound indexes can be optimized - the script will identity redudant indexes and not migrate them to the target. Default: `False`.