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
- Python (version XXX) must be installed.

### Steps to Run the Assessment

1. Download the latest release and unzip it.
2. Open the command prompt and navigate to the extracted directory.
3. Create a JSON file to define the collections to be migrated:

    ```json
    {
       
    }
    ```

4. Run the following command, providing the full path of the JSON file created in the previous step:

    ```cmd
    python schema_transformer.py --config /path/to/config.json
    ```

This process will generate a vCore-optimized schema with index and sharding recommendations based on your workload.
