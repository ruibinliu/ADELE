import os
from dotenv import load_dotenv
load_dotenv()

SESSION_SECRET_KEY = os.getenv("FLASK_SECRET_KEY")
MONGO_URI = os.getenv("MONGO_URI")
LOGIN_URI = os.getenv("LOGIN_URI")
CLIENT_ID = os.getenv("CLIENT_ID")
CLIENT_SECRET = os.getenv("CLIENT_SECRET")
REDIRECT_URI = os.getenv("REDIRECT_URI")
AUTHORIZATION_URI = os.getenv("AUTHORIZATION_URI")
FRONTEND_URI = os.getenv("FRONTEND_URI")
FUNNEL_URI = os.getenv("FUNNEL_URI")
DOWNLOAD_S3 = os.getenv("DOWNLOAD_S3")

FDP_URI = os.getenv("FDP_URI")

API_KEY = os.getenv("API_KEY")
USER_ID = os.getenv("USER_ID")
USER_INFO_URI = os.getenv("USER_INFO_URI")

FDP_ADMIN_USERNAME= os.getenv("FDP_ADMIN_USERNAME")
FDP_ADMIN_PASSWORD= os.getenv("FDP_ADMIN_PASSWORD")
FDP_TRE_CATALOG_URI= os.getenv("FDP_TRE_CATALOG_URI")

API_PORT = os.getenv("API_PORT")

MINIO_ENDPOINT = os.getenv("MINIO_ENDPOINT")
MINIO_SERVICE_ACCOUNT = os.getenv("MINIO_SERVICE_ACCOUNT")
MINIO_SERVICE_ACCOUNT_SECRET = os.getenv("MINIO_SERVICE_ACCOUNT_SECRET")
MINIO_ACCESS_KEY = os.getenv("MINIO_ACCESS_KEY")
MINIO_SECRET_KEY = os.getenv("MINIO_SECRET_KEY")


REMS_URI = os.getenv("REMS_URI", "https://rems.tre.biodata.pt/api")
REMS_API_KEY = os.getenv("REMS_API_KEY")
REMS_USER_ID = os.getenv("REMS_USER_ID")