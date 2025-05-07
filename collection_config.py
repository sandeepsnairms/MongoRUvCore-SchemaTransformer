from dataclasses import dataclass

@dataclass
class CollectionConfig:
    """
    Configuration for a MongoDB collection, including database name, 
    collection name, and various options for sharding and optimization.
    """
    db_name: str
    collection_name: str
    unsharded: bool
    drop_if_exists: bool
    optimize_compound_indexes: bool = False
