from datetime import timedelta
from minio import Minio
import utils
from flask import Blueprint, request, jsonify
import requests
import settings
import fdp_utils
from pymongo import MongoClient
import jwt
import logging
import os
from bson import ObjectId

si_bp = Blueprint('si', __name__)

# Initialize MongoDB client
client = MongoClient(settings.MONGO_URI)
dbProject = client["project"]
projectDB = dbProject["project_details"]

filesDB = dbProject["files"]


# === Audit Logger Setup (reuse the same file as server.py) ===
AUDIT_LOG_FILE = os.path.join(os.path.dirname(__file__), '..', 'audit.log')
audit_logger = logging.getLogger("TRE-BIODATA-AUDIT")
if not audit_logger.hasHandlers():
    audit_logger.setLevel(logging.INFO)
    audit_handler = logging.FileHandler(AUDIT_LOG_FILE, encoding='utf-8')
    audit_handler.setFormatter(logging.Formatter('%(asctime)s %(levelname)s %(message)s'))
    audit_logger.addHandler(audit_handler)

@si_bp.route('/files', methods=['GET'])
def get_files():
    """
    Get a list of files from the FDP.
    """
    user_ip = request.remote_addr
    request_data = request.args.get('id')
    user_id = "unknown"
    audit_logger.info(f"SI_GET_FILES | IP={user_ip} | request_data_present={bool(request_data)}")

    if not request_data:
        audit_logger.warning(f"SI_GET_FILES | MISSING_REQUEST_DATA | IP={user_ip}")
        return jsonify({"error": "No request data provided"}), 400

    try:
        passport = jwt.decode(request_data, options={"verify_signature": False})
        user_id = passport.get('sub', 'unknown')
        audit_logger.info(f"SI_GET_FILES | JWT_DECODED | user_id={user_id} | IP={user_ip}")
    except Exception as e:
        audit_logger.error(f"SI_GET_FILES | INVALID_JWT | IP={user_ip} | error={str(e)}")
        return jsonify({"error": f"Invalid JWT: {str(e)}"}), 401

    visa = passport.get('ga4gh_visa_v1')
    if not visa or visa.get('type') != 'ControlledAccessGrants':
        audit_logger.info(f"SI_GET_FILES | NO_CONTROLLED_ACCESS | user_id={user_id} | IP={user_ip}")
        return jsonify({"dataset": None, "files": []}), 200

    dataset_id = visa.get('value')
    if not dataset_id:
        audit_logger.warning(f"SI_GET_FILES | MISSING_DATASET_ID | user_id={user_id} | IP={user_ip}")
        return jsonify({"error": "Missing dataset value in visa"}), 400

    access_token = request.cookies.get('access_token')
    if not access_token:
        audit_logger.warning(f"SI_GET_FILES | MISSING_ACCESS_TOKEN | user_id={user_id} | IP={user_ip}")
        return jsonify({"error": "Missing access token in cookies"}), 401

    headers = {
        'Authorization': f"Bearer {access_token}",
        'Content-Type': 'application/json'
    }

    try:
        response = requests.get(
            f"{settings.DOWNLOAD_S3}/metadata/datasets/{dataset_id}/files",
            headers=headers,
            timeout=10
        )
        response.raise_for_status()
        audit_logger.info(f"SI_GET_FILES | FILES_FETCHED | user_id={user_id} | dataset_id={dataset_id} | IP={user_ip} | status={response.status_code}")
    except requests.RequestException as e:
        audit_logger.error(f"SI_GET_FILES | FILES_FETCH_FAIL | user_id={user_id} | dataset_id={dataset_id} | IP={user_ip} | error={str(e)}")
        return jsonify({"error": f"Failed to fetch files: {str(e)}"}), 502

    try:
        response_data = response.json()
    except ValueError:
        audit_logger.error(f"SI_GET_FILES | INVALID_JSON_RESPONSE | user_id={user_id} | dataset_id={dataset_id} | IP={user_ip}")
        return jsonify({"error": "Invalid JSON response from file server"}), 502

    files = []
    print(f"Response data: {response_data}")  # Debugging line to check the response structure
    for file in response_data:
        if all(k in file for k in ('fileId', 'displayFileName', 'fileStatus')):
            files.append({
                'id': file['fileId'],
                'status': file['fileStatus']
            })

    audit_logger.info(f"SI_GET_FILES | SUCCESS | user_id={user_id} | dataset_id={dataset_id} | IP={user_ip} | files_count={len(files)}")
    return jsonify({"dataset": dataset_id, "files": files}), 200


@si_bp.route('/files/<file_id>', methods=['GET'])
def get_file(file_id):
    """
    Get details of a specific file from the FDP.
    """
    user_ip = request.remote_addr
    access_token = request.cookies.get('access_token')
    if not access_token:
        audit_logger.warning(f"SI_GET_FILE | MISSING_ACCESS_TOKEN | IP={user_ip}")
        return jsonify({"error": "Missing access token in cookies"}), 401

    headers = {
        'Authorization': f"Bearer {access_token}",
        'Content-Type': 'application/json'
    }

    try:
        response = requests.get(
            f"{settings.DOWNLOAD_S3}/files/{file_id}",
            headers=headers,
            timeout=10
        )
        response.raise_for_status()
        audit_logger.info(f"SI_GET_FILE | FILE_FETCHED | file_id={file_id} | IP={user_ip} | status={response.status_code}")
    except requests.RequestException as e:
        audit_logger.error(f"SI_GET_FILE | FILE_FETCH_FAIL | file_id={file_id} | IP={user_ip} | error={str(e)}")
        return jsonify({"error": f"Failed to fetch file: {str(e)}"}), 502

    try:
        file_data = response.json()
    except ValueError:
        audit_logger.error(f"SI_GET_FILE | INVALID_JSON_RESPONSE | file_id={file_id} | IP={user_ip}")
        return jsonify({"error": "Invalid JSON response from file server"}), 502

    audit_logger.info(f"SI_GET_FILE | SUCCESS | file_id={file_id} | IP={user_ip}")

    
    return jsonify(file_data), 200

@si_bp.route("/generate-presigned-uri/<username>/<filename>", methods=["GET"])
def generate_presigned_uri(username, filename):

    access_token = request.cookies.get('access_token')
    if not access_token:
        return jsonify({"error": "Missing access token in cookies"}), 401
    
    # Decode the JWT to get the current user
    try:
        passport = jwt.decode(access_token, options={"verify_signature": False})
        current_user = passport.get('sub', 'unknown')
    except Exception as e:
        print(f"[ERROR] Failed to decode JWT: {e}")
        return jsonify({"error": "Invalid access token"}), 401
    
    # Initialize MinIO client
    minio_client = Minio(
        settings.MINIO_URI,
        access_key=settings.MINIO_SERVICE_ACCOUNT,
        secret_key=settings.MINIO_SERVICE_ACCOUNT_SECRET,
        secure=False
    )
    if current_user != username:
        return jsonify({"error": "Unauthorized access"}), 403

    object_path = f"{username}/{filename}"

    try:
        uri = minio_client.presigned_get_object(
            "results",                  # bucket name
            object_path,                # path inside bucket
            expires=timedelta(days=1)  # validity of the link
        )
        return jsonify({"uri": uri}), 200

    except Exception as e:
        print(f"[ERROR] {e}")
        return jsonify({"error": str(e)}), 500


@si_bp.route("/upload/file/<filename>", methods=["POST"])
def upload_file(filename):
    """
    Upload a file to the MinIO bucket.
    """
    user_ip = request.remote_addr
    access_token = request.cookies.get('access_token')
    project_id = request.form.get('project_id')
    if not access_token:
        audit_logger.warning(f"SI_UPLOAD_FILE | MISSING_ACCESS_TOKEN | IP={user_ip}")
        return jsonify({"error": "Missing access token in cookies"}), 401

    # Decode the JWT to get the current user
    try:
        passport = jwt.decode(access_token, options={"verify_signature": False})
        current_user = passport.get('sub', 'unknown')
        audit_logger.info(f"SI_UPLOAD_FILE | JWT_DECODED | user_id={current_user} | IP={user_ip}")
    except Exception as e:
        audit_logger.error(f"SI_UPLOAD_FILE | INVALID_JWT | IP={user_ip} | error={str(e)}")
        return jsonify({"error": f"Invalid access token: {str(e)}"}), 401
    
    if not project_id:
        audit_logger.warning(f"SI_UPLOAD_FILE | MISSING_PROJECT_ID | user_id={current_user} | IP={user_ip}")
        return jsonify({"error": "Missing project ID"}), 400

    # Check if the file is provided in the request
    if 'file' not in request.files:
        audit_logger.warning(f"SI_UPLOAD_FILE | MISSING_FILE | user_id={current_user} | IP={user_ip}")
        return jsonify({"error": "No file part in the request"}), 400

    file = request.files['file']
    if file.filename == '':
        audit_logger.warning(f"SI_UPLOAD_FILE | EMPTY_FILENAME | user_id={current_user} | IP={user_ip}")
        return jsonify({"error": "No selected file"}), 400

    #filename = f"{current_user}/{project_id}/{filename}"

    #Contact SDA-API to upload the file for ingestion
    """ sda_api_uri = f"{settings.SDA_API_URI}/upload/file/{filename}"
    try:
        response = requests.post(
            sda_api_uri,
            files={'file': file},
            user=current_user, # update s3cmd marta.felix@lifescience-ri.eu 
            headers={'Authorization': f"Bearer {access_token}"}, #access_token
            timeout=10
        )
        response.raise_for_status()
        audit_logger.info(f"SI_UPLOAD_FILE | FILE_UPLOADED | user_id={current_user} | filename={filename} | IP={user_ip}")
    except requests.RequestException as e:
        audit_logger.error(f"SI_UPLOAD_FILE | UPLOAD_FAIL | user_id={current_user} | filename={filename} | IP={user_ip} | error={str(e)}")
        return jsonify({"error": f"Failed to upload file: {str(e)}"}), 502 """

    #Temporary solution to upload file: upload in tre-shared-documents files between tre and backoffice

    file_id = filesDB.insert_one({
        "filename": filename,
        "user": current_user,
        "project_id": project_id
    })

    file_id = file_id.inserted_id

    audit_logger.info(f"SI_UPLOAD_FILE | FILE_ADDED_TO_DB | user_id={current_user} | file_id={file_id} | IP={user_ip}")

    PROJECT_ROOT = os.path.dirname(os.path.abspath(__file__))
    SHARED_BASE_DIR = os.path.abspath(os.path.join(PROJECT_ROOT, "..", "..", "..", "tre-shared-documents"))
    TEMP_DIR = os.path.join(SHARED_BASE_DIR, "tmp")
    if not os.path.exists(TEMP_DIR):
        os.makedirs(TEMP_DIR)

    file_path = os.path.join(TEMP_DIR, file_id)
    file.save(file_path)


    project = projectDB.find_one({"_id": ObjectId(project_id)})
    if not project:
        audit_logger.warning(f"SI_UPLOAD_FILE | PROJECT_NOT_FOUND | user_id={current_user} | project_id={project_id} | IP={user_ip}")
        return jsonify({"error": "Project not found"}), 404
    
    projectDB.update_one(
        {"_id": ObjectId(project_id)},
        {"$push": {"files": {
            "file_id": file_id
        }}}
    )

    audit_logger.info(f"SI_UPLOAD_FILE | FILE_SAVED_LOCALLY | user_id={current_user} | filename={filename} | IP={user_ip}")

    return jsonify({"message": "File uploaded successfully"}), 200