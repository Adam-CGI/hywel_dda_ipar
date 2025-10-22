"""
Configuration module for Hywel Dda IPAR Document Miner
Loads environment variables and initializes Azure service clients.
"""
import os
from dotenv import load_dotenv
from azure.storage.blob import BlobServiceClient
from azure.cosmos import CosmosClient
from azure.ai.formrecognizer import DocumentAnalysisClient
from azure.core.credentials import AzureKeyCredential
from opencensus.ext.azure.log_exporter import AzureLogHandler
import logging

# Load environment variables
load_dotenv()

# Application settings
FLASK_ENV = os.getenv("FLASK_ENV", "development")
PORT = int(os.getenv("PORT", 8000))

# Azure Resource Group
RESOURCE_GROUP = os.getenv("RESOURCE_GROUP")
SUBSCRIPTION_ID = os.getenv("SUBSCRIPTION_ID")
LOCATION = os.getenv("LOCATION", "uksouth")

# Azure Storage
AZURE_STORAGE_CONNSTR = os.getenv("AZURE_STORAGE_CONNSTR")
AZURE_STORAGE_ACCOUNT = os.getenv("AZURE_STORAGE_ACCOUNT")
CONTAINER_RAW = os.getenv("AZURE_STORAGE_CONTAINER_RAW", "raw")
CONTAINER_EXTRACTED = os.getenv("AZURE_STORAGE_CONTAINER_EXTRACTED", "extracted")
CONTAINER_THUMBS = os.getenv("AZURE_STORAGE_CONTAINER_THUMBS", "thumbs")
CONTAINER_MANIFESTS = os.getenv("AZURE_STORAGE_CONTAINER_MANIFESTS", "manifests")
CONTAINER_ARCHIVE = os.getenv("AZURE_STORAGE_CONTAINER_ARCHIVE", "archive")

# Azure AI Search
AZURE_SEARCH_ENDPOINT = os.getenv("AZURE_SEARCH_ENDPOINT")
AZURE_SEARCH_ADMIN_KEY = os.getenv("AZURE_SEARCH_ADMIN_KEY")
AZURE_SEARCH_INDEX = os.getenv("AZURE_SEARCH_INDEX", "ipar-chunks")

# Azure OpenAI
AZURE_OPENAI_ENDPOINT = os.getenv("AZURE_OPENAI_ENDPOINT")
AZURE_OPENAI_API_KEY = os.getenv("AZURE_OPENAI_API_KEY")
AZURE_OPENAI_EMBED_DEPLOYMENT = os.getenv("AZURE_OPENAI_EMBED_DEPLOYMENT", "text-embedding-3-large")
AZURE_OPENAI_CHAT_DEPLOYMENT = os.getenv("AZURE_OPENAI_CHAT_DEPLOYMENT", "gpt-4o-mini")

# Document Intelligence
AZURE_DOCINTEL_ENDPOINT = os.getenv("AZURE_DOCINTEL_ENDPOINT")
AZURE_DOCINTEL_KEY = os.getenv("AZURE_DOCINTEL_KEY")

# Cosmos DB
COSMOS_ENDPOINT = os.getenv("COSMOS_ENDPOINT")
COSMOS_KEY = os.getenv("COSMOS_KEY")
COSMOS_DB = os.getenv("COSMOS_DB", "ipar")
COSMOS_COLL_DOCUMENTS = os.getenv("COSMOS_COLL_DOCUMENTS", "documents")
COSMOS_COLL_LINEAGE = os.getenv("COSMOS_COLL_LINEAGE", "lineage")
COSMOS_COLL_EVENTS = os.getenv("COSMOS_COLL_EVENTS", "events")
COSMOS_COLL_USERS = os.getenv("COSMOS_COLL_USERS", "users")

# Application Insights
APPLICATIONINSIGHTS_CONNECTION_STRING = os.getenv("APPLICATIONINSIGHTS_CONNECTION_STRING")

# Authentication (External ID)
AUTH_PROVIDER = os.getenv("AUTH_PROVIDER", "external-id")
EXTERNAL_ID_TENANT = os.getenv("EXTERNAL_ID_TENANT")
EXTERNAL_ID_CLIENT_ID = os.getenv("EXTERNAL_ID_CLIENT_ID")
EXTERNAL_ID_ISSUER = os.getenv("EXTERNAL_ID_ISSUER")
EXTERNAL_ID_POLICY = os.getenv("EXTERNAL_ID_POLICY")


# Initialize Azure clients
def get_blob_service_client():
    """Initialize and return Azure Blob Storage client."""
    if not AZURE_STORAGE_CONNSTR:
        raise ValueError("AZURE_STORAGE_CONNSTR not configured")
    return BlobServiceClient.from_connection_string(AZURE_STORAGE_CONNSTR)


def get_cosmos_client():
    """Initialize and return Cosmos DB client."""
    if not COSMOS_ENDPOINT or not COSMOS_KEY:
        raise ValueError("COSMOS_ENDPOINT or COSMOS_KEY not configured")
    return CosmosClient(COSMOS_ENDPOINT, credential=COSMOS_KEY)


def get_document_intelligence_client():
    """Initialize and return Azure Document Intelligence client."""
    if not AZURE_DOCINTEL_ENDPOINT or not AZURE_DOCINTEL_KEY:
        raise ValueError("AZURE_DOCINTEL_ENDPOINT or AZURE_DOCINTEL_KEY not configured")
    return DocumentAnalysisClient(
        endpoint=AZURE_DOCINTEL_ENDPOINT,
        credential=AzureKeyCredential(AZURE_DOCINTEL_KEY)
    )


def get_cosmos_database():
    """Get Cosmos DB database instance."""
    client = get_cosmos_client()
    return client.get_database_client(COSMOS_DB)


def get_cosmos_container(container_name):
    """Get Cosmos DB container instance."""
    database = get_cosmos_database()
    return database.get_container_client(container_name)


# Configure logging
def configure_logging():
    """Configure application logging with Azure Application Insights."""
    logger = logging.getLogger(__name__)
    logger.setLevel(logging.INFO)
    
    # Console handler
    console_handler = logging.StreamHandler()
    console_handler.setLevel(logging.INFO)
    formatter = logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s')
    console_handler.setFormatter(formatter)
    logger.addHandler(console_handler)
    
    # Azure Application Insights handler
    if APPLICATIONINSIGHTS_CONNECTION_STRING:
        try:
            azure_handler = AzureLogHandler(connection_string=APPLICATIONINSIGHTS_CONNECTION_STRING)
            azure_handler.setLevel(logging.INFO)
            logger.addHandler(azure_handler)
        except Exception as e:
            logger.warning(f"Failed to initialize Azure Application Insights: {e}")
    
    return logger


# Initialize logger
logger = configure_logging()
