import os
from dotenv import load_dotenv
load_dotenv()

FUNNEL_URI = os.getenv("FUNNEL_URI")
MONGO_URI = os.getenv("MONGO_URI")
BACKEND_PORT = os.getenv("BACKEND_PORT", 8081)

FRONTEND_URI = os.getenv("FRONTEND_URI")

MINIO_URI = os.getenv("MINIO_URI")
MINIO_ACCESS_KEY = os.getenv("MINIO_ACCESS_KEY")
MINIO_SECRET_KEY = os.getenv("MINIO_SECRET_KEY")

SI_API_URI = os.getenv("SI_API_URI")

REMS_API_KEY = os.getenv("REMS_API_KEY")
REMS_USER_ID = os.getenv("REMS_USER_ID")

REMS_API = os.getenv("REMS_API")