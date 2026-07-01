# Schema Transformer: Migrating RU-based Azure Cosmos DB for MongoDB to Azure DocumentDB

Schema Transformer is a Python script designed to analyze Mongo RU Collection schemas and efficiently transform them into a DocumentDB optimized structure. This ensures seamless compatibility and enhances query performance.

With this tool, you can generate index and sharding recommendations tailored specifically to your workload, making your migration smoother and more efficient.

## Supported Versions

The tool supports the following versions:

- **Source:** Azure Cosmos DB for MongoDB RU-based (version 4.2 and above)
- **Target:** Azure DocumentDB (all versions)

## How to Run the Script

### Prerequisites

Before running the assessment, ensure that the client machine meets the following requirements:

- Access to both source MongoDB RU endpoint and target Azure DocumentDb endpoint, either over a private or public network via the specified IP or hostname.
- Python (version 3.10 or above) must be installed.
- PyMongo library must be installed (`pip install pymongo`).

### Steps to Run the Assessment

1. Download the latest [release](https://github.com/AzureCosmosDB/MongoRUvCore-SchemaTransformer/releases) and unzip it.
2. Open the command prompt and navigate to the extracted directory.
3. Create a JSON file to define the collections to be migrated. Each section in the configuration will define the schema migration options for a set of collections (you can specify `*` to refer to all collections in an account and `db.*` to refer all collections within a database). Refer the next section for more details on configuration options. Here are some examples -

    1. To specify all collections present in the account
    
        ```json
        {
            "sections": [
                {
                    "include": [
                        "*"
                    ],
                    "exclude": [],
                    "migrate_shard_key": "false",
                    "drop_if_exists": "true",
                    "optimize_compound_indexes": "true"
                }
            ]
        }
        ```
    2. To specify all collections except a particular database
    
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
                    "migrate_shard_key": "false",
                    "drop_if_exists": "true",
                    "optimize_compound_indexes": "true"
                }
            ]
        }
        ```

    3. To specify all collections except few
    
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
                    "migrate_shard_key": "false",
                    "drop_if_exists": "true",
                    "optimize_compound_indexes": "true"
                }
            ]
        }
        ```

    4. To migrate specific collections
    
        ```json
        {
            "sections": [
                {
                    "include": [
                        "db1.coll1",
                        "db2.coll2"
                    ],
                    "migrate_shard_key": "false",
                    "drop_if_exists": "true",
                    "optimize_compound_indexes": "true"
                }
            ]
        }
        ```

    5. To migrate different set of collections with different configuration options
    
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
                    "migrate_shard_key": "false",
                    "drop_if_exists": "true",
                    "optimize_compound_indexes": "true"
                },
                {
                    "include": [
                        "db1.coll1",
                        "db2.coll2"
                    ],
                    "migrate_shard_key": "true",
                    "drop_if_exists": "true",
                    "optimize_compound_indexes": "true"
                }
            ]
        }
        ```

    6. To colocate collections with a reference collection
    
        ```json
        {
            "sections": [
                {
                    "include": [
                        "db1.coll2",
                        "db1.coll3"
                    ],
                    "migrate_shard_key": "false",
                    "drop_if_exists": "true",
                    "optimize_compound_indexes": "true",
                    "co_locate_with": "coll1"
                }
            ]
        }
        ```
        
        **Note:** The collection specified in `co_locate_with` must already exist in the same database as the collection being processed. If the reference collection is not found, the script will fail with an error.

4. Run the following command, providing the full path of the JSON file created in the previous step:

    ```cmd
    python main.py --config <path_to_your_json_file> --source-uri <source_mongo_connection_string> --dest-uri <destination_connection_string>
    ```

    **Optional: Control index migration strategy** using the `--mode` parameter:

    ```cmd
    # Pre-ingestion phase (create unique indexes only, before data migration)
    python main.py --config <path_to_your_json_file> --source-uri <source> --dest-uri <dest> --mode preIngestion

    # Post-ingestion phase (create non-unique indexes only, after data migration)
    python main.py --config <path_to_your_json_file> --source-uri <source> --dest-uri <dest> --mode postIngestion

    # Post-ingestion with blocking index builds
    python main.py --config <path_to_your_json_file> --source-uri <source> --dest-uri <dest> --mode postIngestion --blocking
    ```

    The `--mode` flag controls which indexes are created:
    - `complete` (default): Creates all indexes (both unique and non-unique).
    - `preIngestion`: Creates only unique indexes. Run this **before** data ingestion so that uniqueness is enforced while data is being loaded.
    - `postIngestion`: Creates only non-unique indexes. In this mode, drop/create, colocation and shard-key migration are **skipped**, and indexes that already exist on the destination are also skipped. Run this **after** data ingestion completes.

This process will generate an Azure DocumentDB-optimized schema with index and sharding recommendations based on your workload.

### Index Migration Modes

The tool supports three index migration modes so you can split index creation across the data-migration lifecycle:

#### 1. `complete` (default)
Creates all indexes (unique and non-unique) in a single pass. Best when downtime is acceptable or the dataset is small.

#### 2. `preIngestion`
Creates only unique indexes before data is ingested. Non-unique indexes are skipped. Typical workflow:

1. Run the tool with `--mode preIngestion` against the empty destination.
2. Migrate data from source to destination using your data-migration tool of choice.
3. Run the tool again with `--mode postIngestion` to create the remaining indexes.

#### 3. `postIngestion`
Creates only non-unique indexes after data is in place. Schema-level operations are skipped:
- No collection drop / recreate
- No collection creation
- No colocation changes
- No shard-key migration
- Indexes that already exist on the destination are detected and skipped

When using `postIngestion`, you can optionally pass `--blocking` to build indexes with the `createIndexes` command using `blocking: true`.

> ### ⚠️ CRITICAL WARNING — `--blocking` STOPS WRITES
>
> **Blocking index builds take an EXCLUSIVE LOCK on the target collection for the entire duration of the build.**
>
> - **All writes to the target collections MUST be stopped BEFORE running with `--blocking`.**
> - **Any write issued while a blocking build is in progress WILL FAIL.**
> - Stop application traffic, ingestion / migration jobs, and any other writers to the destination collections before proceeding.
> - `main.py` will show a warning banner and require you to type `yes` to confirm writes have been stopped before it starts.
>
> Only use `--blocking` when you have exclusive control over the destination collections and can accept a write outage for the length of the index build. If you cannot stop writes, omit `--blocking` and let the tool build indexes without the exclusive lock.

Refer to the [Azure Cosmos DB documentation on prioritizing index builds](https://learn.microsoft.com/en-us/azure/documentdb/how-to-create-indexes#prioritizing-index-builds-over-new-write-operations-using-the-blocking-option) for details on the blocking option.

**Example end-to-end workflow:**

```bash
# Step 1: pre-ingestion — create unique indexes only
python main.py --config config.json --source-uri <source> --dest-uri <dest> --mode preIngestion

# Step 2: migrate data (using your data migration tool)

# Step 3: STOP all writes to the destination collections, then create the rest of the
#         indexes with blocking builds
python main.py --config config.json --source-uri <source> --dest-uri <dest> --mode postIngestion --blocking
```


### Configuration Options

| **Option** | **Description** |
|-----------|---------------|
| **migrate_shard_key** | Determines whether the existing shard key definition should be migrated. If set to `True`, the shard key is retained; if `False`, the target collection remains unsharded. Collections that are originally unsharded in the source will remain unsharded in the target, regardless of this setting. **Default:** `False`. |
| **drop_if_exists** | Specifies whether collections with the same name in the target should be dropped and recreated. If `True`, existing collections are removed before migration; if `False`, they remain unchanged. **Default:** `False`. |
| **optimize_compound_indexes** | Controls whether compound indexes should be optimized. If `True`, the script identifies redundant indexes and excludes them from migration; if `False`, all indexes are migrated as-is. **Default:** `False`. |
| **co_locate_with** | Specifies the name of a reference collection from the same database to colocate with. When specified, the target collection will be colocated with the reference collection for improved query performance. The reference collection must exist in the same database before colocation is applied, or an error will be thrown. This option is useful for optimizing queries that join or access related collections together. **Default:** `None`. |

### Command Line Options

| **Option** | **Required** | **Description** |
|-----------|-------------|---------------|
| **--config-file** | Yes | Path to the JSON configuration file. |
| **--source-uri** | Yes | Source MongoDB (Cosmos DB for MongoDB RU) connection string. |
| **--dest-uri** | Yes | Destination (Azure DocumentDB) connection string. |
| **--mode** | No | Index migration mode: `complete` (default), `preIngestion`, or `postIngestion`. See the *Index Migration Modes* section. |
| **--blocking** | No | (postIngestion only) Build indexes with `createIndexes` `blocking: true`. **Takes an exclusive lock — writes to the target collections must be stopped before use, or they will fail.** |
