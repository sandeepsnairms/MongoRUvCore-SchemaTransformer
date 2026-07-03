"""Entra ID (Microsoft Entra) authentication helpers for the destination
Azure DocumentDB connection.

Uses ``DefaultAzureCredential`` from ``azure-identity`` to obtain a token for
the identity of the environment the script is running under. That identity
must already be enabled and authorized on the destination Azure DocumentDB.
"""

from pymongo import MongoClient
from pymongo.auth_oidc import OIDCCallback, OIDCCallbackResult

# Resource / audience used by Azure DocumentDB for Entra ID tokens.
_DOCUMENTDB_SCOPE = "https://ossrdbms-aad.database.windows.net/.default"


class _AzureIdentityOIDCCallback(OIDCCallback):
    """OIDC callback that returns an Entra ID access token from
    ``DefaultAzureCredential`` on each driver request."""

    def __init__(self):
        # Imported lazily so the dependency is only required when Entra ID auth
        # is actually requested.
        from azure.identity import DefaultAzureCredential

        self._credential = DefaultAzureCredential()

    def fetch(self, context):  # noqa: ARG002 - context is required by the interface
        token = self._credential.get_token(_DOCUMENTDB_SCOPE)
        return OIDCCallbackResult(access_token=token.token)


def create_entra_id_mongo_client(uri: str) -> MongoClient:
    """Create a ``MongoClient`` that authenticates to the destination Azure
    DocumentDB using Microsoft Entra ID via ``DefaultAzureCredential``.

    The script must be run from an environment whose identity has been
    enabled and authorized on the destination Azure DocumentDB. The ``uri``
    should be the Entra ID style connection string for the target cluster
    (no username / password embedded). The MONGODB-OIDC mechanism and OIDC
    callback are supplied here, so the caller does not need to encode them in
    the URI.
    """
    return MongoClient(
        uri,
        authMechanism="MONGODB-OIDC",
        authMechanismProperties={"OIDC_CALLBACK": _AzureIdentityOIDCCallback()},
    )
