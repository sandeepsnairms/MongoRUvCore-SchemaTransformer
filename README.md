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
- To authenticate the destination with Microsoft Entra ID (recommended), also install `azure-identity` (`pip install azure-identity`). The script must be run from an environment whose identity has already been **enabled and authorized on the destination Azure DocumentDB** with the data-plane permissions required to create collections / indexes on the target. `DefaultAzureCredential` will pick up that identity at runtime.

### Steps to Run the Assessment

1. Download the latest [release](https://github.com/AzureCosmosDB/MongoRUvCore-SchemaTransformer/releases) and unzip it.
2. Open the command prompt and navigate to the extracted directory.
3. Create a JSON file to define the collections to be migrated. Each section in the configuration will define the schema migration options for a set of collections (you can specify `*` to refer to all collections in an account and `db.*` to refer all collections within a database). Refer the next section for more details on configuration options. Before choosing the settings, consider the following schema-design guidance:

    > **Target cluster setup:** This script does not provision or resize an Azure DocumentDB cluster, select its storage type, change its compute tier, or add physical shards. Review the storage, compute, and scale recommendations below and, if needed, modify the Azure DocumentDB migration target before running this script. Complete changes such as selecting Premium SSD v2, increasing storage or compute, or adding physical shards directly on the target cluster first. This script then configures collection schema, indexes, shard-key migration, and collection placement on the target cluster you provide.

    **When to migrate a collection as unsharded**

    Start with `migrate_shard_key: "false"` when all of the following are true:

    - The source collection is sharded only because of the Azure Cosmos DB for MongoDB 20-GB logical partition limit, especially when its current shard key is `_id`. That limit does not apply to Azure DocumentDB, so retaining `_id` as the shard key can add cross-shard work for queries that do not filter on `_id`, without providing a target-side benefit.
    - The collection's projected size, including documents, indexes, migration growth, and an operational buffer, fits on the disk of one physical shard. An unsharded collection that fits on the selected disk is a good migration choice; Azure DocumentDB supports disks as large as 32 TB per physical shard.
    - A representative load test shows that one shard can sustain peak reads and writes at the required latency. As a planning signal, CPU should remain below 70% for prolonged periods, with no saturation of memory, storage IOPS, or bandwidth.

    Choose `migrate_shard_key: "true"` when the projected collection size cannot fit on one physical shard, or when load testing shows that a single shard cannot meet the required throughput and latency after selecting an appropriate compute tier. Do not use a fixed transactions-per-second (TPS) cutoff: a request that reads one small indexed document has a very different cost from a write with several indexes or a cross-collection aggregation.

    **Example: planning for an 8-TB physical shard**

    Assume each destination physical shard has 8 TB of provisioned storage:

    | Projected collection size | Recommended starting decision |
    |---------------------------|-------------------------------|
    | Up to 5.6 TB, including indexes and expected growth | Prefer unsharded when one shard meets the workload's throughput and latency requirements. The 5.6-TB value is 70% of the provisioned 8 TB and leaves capacity for growth and operational overhead. |
    | More than 5.6 TB and up to 8 TB | The collection can remain unsharded because it fits on the disk. Plan a storage increase as usage crosses 70% so indexes, growth, and maintenance operations do not exhaust the available capacity. |
    | More than 8 TB | The collection cannot fit on the selected 8-TB disk. Configure the migration target with more storage and keep the collection unsharded if it then fits and meets performance requirements; otherwise, migrate it as a sharded collection. |

    For example, suppose a source collection is sharded on `_id`, is projected to occupy 3 TB including indexes and two years of growth, and peaks at 20,000 application operations per second. Load test the destination at or above that peak, for example at 30,000 operations per second. If sustained CPU remains below 70%, IOPS and bandwidth do not saturate, and latency meets the application's target, migrate it as unsharded. If the test at 20,000 operations per second already drives sustained CPU above 70% or misses the latency target, first configure and test a larger compute tier on the migration target; shard only when one appropriately sized physical shard still cannot serve the workload.

    When setting up the migration target, consider Premium SSD v2, which can provide up to 80,000 IOPS and 1,200 MB/s subject to the selected compute tier. Premium SSD v2 must be selected on the Azure DocumentDB cluster; this script does not enable it. These values are storage operations, not application TPS, so do not compare them directly with the application's requests-per-second count. See the Azure guidance for [sharding](https://learn.microsoft.com/azure/documentdb/partitioning#best-practices-for-sharding-data), [compute and storage sizing](https://learn.microsoft.com/azure/documentdb/compute-storage#considerations-for-compute-and-storage), and [Premium SSD v2 limits](https://learn.microsoft.com/azure/documentdb/high-performance-storage#iops-and-throughput-caps).

    **Choose single-node or multi-node placement**

    Multiple collections or databases do not by themselves require multiple physical shards. Start with a single physical shard when the combined projected storage of all collections, including indexes and growth headroom, fits on its disk and the shard can meet the aggregate throughput and latency requirements.

    **Provision additional physical shards on the migration target before running this script, and only when the total storage or measured workload requires scale-out. This script does not add or remove physical shards.**

    When using multiple physical shards:

    - **Understand the default placement.** By default, Azure DocumentDB places all collections in a database on the same physical shard. In a multi-node cluster, this can concentrate that database's storage and request load on one node.
    - **Balance independent collections.** Use `move_to` to move selected unsharded collections to other physical shards so that storage, request volume, and memory pressure are balanced and no shard becomes a hotspot.
    - **Keep related collections together.** Collections referenced together by operations such as `$lookup`, `$graphLookup`, or `$unionWith` should remain on the same destination shard. When the destination shard name is known, use the same `move_to` value for each related collection. Use `co_locate_with` when the reference collection already exists but you do not know which shard contains it.

    For example, suppose capacity planning and load testing show that the combined workload requires three physical shards, each provisioned with 8 TB. The following collections all belong to the same database and would therefore be placed together by default unless their placement is explicitly changed:

    | Collection | Projected size | Peak workload | Placement decision |
    |------------|----------------|---------------|--------------------|
    | `orders` | 3 TB | 20,000 operations/second | Keep unsharded and use `move_to: "shard_0"`. |
    | `customers` | 1 TB | 8,000 operations/second | Keep unsharded and use `move_to: "shard_1"`. |
    | `customerProfiles` | 0.5 TB | 3,000 operations/second; frequently joined to `customers` with `$lookup` | Keep unsharded and use `move_to: "shard_1"`, matching `customers`. If `customers` already exists but its shard name is unknown, use `co_locate_with: "customers"` instead. |
    | `auditEvents` | 2 TB | 15,000 operations/second | Keep unsharded and use `move_to: "shard_2"`. |

    This explicit layout overrides the default database-level placement. It keeps the related `customers` and `customerProfiles` collections together while spreading the independent high-volume collections across the other physical shards. When using `co_locate_with`, create or migrate the reference collection first; the option discovers and uses that collection's current shard. Validate the final layout with load tests: equal storage alone does not guarantee equal load, so adjust placement if one shard has materially higher sustained CPU, IOPS, latency, or request volume.

    Here are some configuration examples:

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
        
        **Note:** Use `co_locate_with` when the reference collection already exists in the same database but its destination shard name is unknown. If the shard name is known, `move_to` can place both collections on that shard directly. If the reference collection is not found, the script will fail with an error.

    7. To pin unsharded collections to a specific destination shard

        ```json
        {
            "sections": [
                {
                    "include": [
                        "db1.coll1",
                        "db1.coll2"
                    ],
                    "migrate_shard_key": "false",
                    "drop_if_exists": "true",
                    "optimize_compound_indexes": "true",
                    "move_to": "shard_0"
                }
            ]
        }
        ```

        **Note:** `move_to` issues `db.adminCommand({ moveCollection: "<db>.<coll>", toShard: "<value>" })` on the destination after the collection is created and its indexes are applied. It cannot be combined with `migrate_shard_key: "true"` — a sharded collection cannot be pinned to a single shard, and the configuration will be rejected at parse time. If the collection already resides on the requested shard, the move is treated as a no-op. This option is ignored in `postIngestion` mode since collection drop/create is skipped.

        **Tip:** To discover the valid shard names to use as the `move_to` value, run the following against the destination cluster:

        ```javascript
        db.adminCommand({ listShards: 1 })
        ```

        Use the `_id` field of each returned shard document as the `move_to` value.

4. Run the following command, providing the full path of the JSON file created in the previous step:

    ```cmd
    python main.py --config <path_to_your_json_file> --source-uri <source_mongo_connection_string> --dest-uri <destination_connection_string>
    ```

    **Optional: Authenticate the destination with Microsoft Entra ID** using `--dest-auth-entra-id`. When this flag is set, `--dest-uri` must be the Entra ID style connection string for the target cluster (no username / password embedded), and the script must be run from an environment whose identity has been enabled on the destination Azure DocumentDB. The tool will obtain an access token via `DefaultAzureCredential` for that identity:

    ```cmd
    python main.py --config <path_to_your_json_file> --source-uri <source_mongo_connection_string> --dest-uri <entra_id_connection_string> --dest-auth-entra-id
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
| **co_locate_with** | Specifies an existing reference collection from the same database whose physical shard should be used when that shard's name is unknown. The reference collection must exist before colocation is applied, or an error will be thrown. When the shard name is known, use the same `move_to` value for the related collections instead. **Default:** `None`. |
| **move_to** | Pins an unsharded collection to a specific destination shard by issuing `db.adminCommand({ moveCollection: "<db>.<coll>", toShard: "<value>" })` after the collection is created and its indexes are applied. Cannot be combined with `migrate_shard_key: "true"` (the configuration will be rejected at parse time). If the collection is already on the requested shard, the move is silently skipped. Ignored in `postIngestion` mode since collection drop/create is skipped. **Default:** `None`. |

### Command Line Options

| **Option** | **Required** | **Description** |
|-----------|-------------|---------------|
| **--config-file** | Yes | Path to the JSON configuration file. |
| **--source-uri** | Yes | Source MongoDB (Cosmos DB for MongoDB RU) connection string. |
| **--dest-uri** | Yes | Destination (Azure DocumentDB) connection string. |
| **--mode** | No | Index migration mode: `complete` (default), `preIngestion`, or `postIngestion`. See the *Index Migration Modes* section. |
| **--blocking** | No | (postIngestion only) Build indexes with `createIndexes` `blocking: true`. **Takes an exclusive lock — writes to the target collections must be stopped before use, or they will fail.** |
| **--dest-auth-entra-id** | No | Authenticate to the destination Azure DocumentDB using Microsoft Entra ID via `DefaultAzureCredential`. The script must be run from an environment whose identity has been enabled and authorized on the destination Azure DocumentDB. When set, `--dest-uri` must be the Entra ID style connection string for the target cluster (no username / password embedded). |
