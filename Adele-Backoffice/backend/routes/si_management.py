from flask import Blueprint, request, jsonify, session
from minio import Minio
import requests
from config.settings import * 
from minio.commonconfig import CopySource
from routes.tasks_management import updateTaskStatus
from config.audit_logger import audit_logger
import os

si_management_bp = Blueprint('si_management', __name__)

# Initialize MinIO client
minio_client = Minio(
    MINIO_URI,
    access_key=MINIO_ACCESS_KEY,
    secret_key=MINIO_SECRET_KEY,
    secure=False
)

TES_BUCKET = "tes"
RESULTS_BUCKET = "results"

@si_management_bp.route('/get/output/list', methods=['GET'])
def get_output_list():
    user_id = session.get('user_id', 'unknown')
    username = session.get('username', 'unknown')
    try:
        print("[DEBUG] Listing objects in TES_BUCKET...")
        files = []
        objects = minio_client.list_objects(TES_BUCKET, recursive=True)
        for obj in objects:
            print(f"[DEBUG] Found object: {obj.object_name}")
            files.append(obj.object_name)
        print(f"[DEBUG] Total files found in {TES_BUCKET} bucket: {len(files)}")
        audit_logger.info(f"GET_OUTPUT_LIST | SUCCESS | user_id={user_id} | username={username} | IP={request.remote_addr} | files={len(files)}")
        return jsonify({"files": files}), 200
    except Exception as e:
        print(f"[ERROR] Exception in get_output_list: {e}")
        audit_logger.warning(f"GET_OUTPUT_LIST | ERROR | user_id={user_id} | username={username} | IP={request.remote_addr} | error={str(e)}")
        return jsonify({"error": str(e)}), 500
    
@si_management_bp.route('/view/<user>/<filename>', methods=['GET'])
def view_user_filename(user, filename):
    user_id = session.get('user_id', 'unknown')
    username = session.get('username', 'unknown')
    try:
        object_path = f"{user}/{filename}"
        response = minio_client.get_object(TES_BUCKET, object_path)
        data = response.read().decode("utf-8")
        response.close()
        response.release_conn()
        audit_logger.info(f"VIEW_FILE | SUCCESS | user_id={user_id} | username={username} | IP={request.remote_addr} | file={object_path}")
        return jsonify({"content": data}), 200
    except Exception as e:
        audit_logger.warning(f"VIEW_FILE | ERROR | user_id={user_id} | username={username} | IP={request.remote_addr} | file={object_path} | error={str(e)}")
        return jsonify({"error": str(e)}), 500
    
@si_management_bp.route('/approve/<user>/<filename>', methods=['POST'])
def approve_file(user, filename):
    user_id = session.get('user_id', 'unknown')
    username = session.get('username', 'unknown')
    try:
        source = CopySource(
            bucket_name=TES_BUCKET,
            object_name=f"{user}/{filename}"
        )
        dest_path = f"{user}/{filename}"
        minio_client.copy_object(
            RESULTS_BUCKET,
            dest_path,
            source
        )
        minio_client.remove_object(TES_BUCKET, f"{user}/{filename}")
        print(f"[DEBUG] File {filename} approved and moved to {RESULTS_BUCKET}/{dest_path}")
        filename_without_extension, ext = os.path.splitext(filename)
        pipeline = filename_without_extension.split("-")[1]
        filename = filename_without_extension.replace(f"-{pipeline}", "")
        updateTaskStatus(user, filename, pipeline, "COMPLETED")
        audit_logger.info(f"APPROVE_FILE | SUCCESS | user_id={user_id} | username={username} | IP={request.remote_addr} | file={dest_path}")
        return jsonify({"message": "File approved and moved successfully."}), 200
    except Exception as e:
        audit_logger.warning(f"APPROVE_FILE | ERROR | user_id={user_id} | username={username} | IP={request.remote_addr} | file={filename} | error={str(e)}")
        return jsonify({"error": str(e)}), 500

@si_management_bp.route('/reject/<user>/<filename>', methods=['POST'])
def reject_file(user, filename):
    user_id = session.get('user_id', 'unknown')
    username = session.get('username', 'unknown')
    try:
        object_path = f"{user}/{filename}"
        minio_client.remove_object(TES_BUCKET, object_path)
        audit_logger.info(f"REJECT_FILE | SUCCESS | user_id={user_id} | username={username} | IP={request.remote_addr} | file={object_path}")
        return jsonify({"message": "File rejected and deleted successfully."}), 200
    except Exception as e:
        audit_logger.warning(f"REJECT_FILE | ERROR | user_id={user_id} | username={username} | IP={request.remote_addr} | file={object_path} | error={str(e)}")
        return jsonify({"error": str(e)}), 500

def update_rems(dataset_id, rems_item_name):
    """
    Create a REMS resource and catalogue item for the given dataset.
    Returns True if successful, False otherwise.
    """
    payload = {
        "resid": dataset_id,
        "organization": {
            "organization/id": "adele-tre"
        },
        "licenses": [1]
    }

    headers = {
        'Content-Type': 'application/json',
        'x-rems-user-id': REMS_USER_ID,
        'x-rems-api-key': REMS_API_KEY
    }

    try:
        response = requests.post(REMS_API + "/resources/create", json=payload, headers=headers)
        print(f"[DEBUG] REMS API response: {response.status_code} - {response.text}")
        if response.ok and response.json().get("success", False):
            resource_id = response.json().get('id')
            print (f"[DEBUG] Created REMS resource with ID: {resource_id}")
            payload = {
                "resid": resource_id,
                "wfid": 1,
                "organization": {
                    "organization/id": "adele-tre"
                },
                "localizations": {
                    "en": {
                        "title": rems_item_name,
                    }
                },
                "enabled": True,
                "archived": False
            }
            response = requests.post(REMS_API + "/catalogue-items/create", json=payload, headers=headers)
            print(f"[DEBUG] REMS Catalogue API response: {response.status_code} - {response.text}")
            if response.ok and response.json().get("success", False):
                return True
            else:
                print("Failed to add file to REMS resource:", response.text)
                return False
        else:
            print("Failed to create REMS resource:", response.text)
            return False
    except Exception as e:
        print(f"[ERROR] Exception in update_rems: {e}")
        return False

@si_management_bp.route('/get-queue-files', methods=['GET'])
def get_queue_files():
    """
    Get the list of files in the SI ingest queue.
    """

    try:
        response = requests.post(SI_API_URI + "/ingest/list")
        print(f"[DEBUG] SI API response: {response.status_code} - {response.text}")
        return jsonify(response.json()), response.status_code
    except Exception as e:
        print(f"[ERROR] Failed to get queue files: {e}")
        return jsonify({"error": str(e)}), 500

@si_management_bp.route('/ingest', methods=['POST'])
def ingest_file():
    """
    Process a file from the SI queue.
    """
    print("[DEBUG] Ingesting file. Request data:", request.json)
    try:
        filename = request.json.get('filename')
        if not filename:
            return jsonify({"error": "File name is required"}), 400

        unique_id = request.json.get('unique_id')
        if not unique_id:
            return jsonify({"error": "Unique ID is required"}), 400

        dataset_id = request.json.get('dataset_id')
        if not dataset_id:
            return jsonify({"error": "Dataset ID is required"}), 400

        rems_item_name = request.json.get('rems_item_name', filename)
        if not rems_item_name:
            return jsonify({"error": "REMS item name is required"}), 400

        # Ingest file
        response = requests.post(SI_API_URI + "/ingest", json={"file_name": filename})
        print(f"[DEBUG] SI API response to Ingest: {response.status_code} - {response.text}")
        if response.status_code != 200:
            return jsonify({"error": "Failed to ingest file"}), response.status_code

        # Accession file
        response = requests.post(SI_API_URI + "/accession/", json={"file_name": filename, "unique_id": unique_id})
        print(f"[DEBUG] SI API response to Accession: {response.status_code} - {response.text}")
        if response.status_code != 200:
            return jsonify({"error": "Failed to accession file"}), response.status_code

        # Create dataset
        response = requests.post(SI_API_URI + "/dataset/", json={"file_name": filename, "dataset_id": dataset_id})
        print(f"[DEBUG] SI API response to Create Dataset: {response.status_code} - {response.text}")
        if response.status_code != 200:
            return jsonify({"error": "Failed to create dataset"}), response.status_code

        # Update REMS
        rems_success = update_rems(dataset_id, rems_item_name)
        if not rems_success:
            return jsonify({"error": "Failed to update REMS resource"}), 500

        return jsonify({"message": "File processed successfully"}), 200

    except Exception as e:
        print(f"[ERROR] Exception in process_file: {e}")
        return jsonify({"error": str(e)}), 500


@si_management_bp.route('/get/files', methods=['GET'])
def get_file():
    user_id = session.get('user_id', 'unknown')
    username = session.get('username', 'unknown')
    
    #Temporary implementation to return a static list of files
    PROJECT_ROOT = os.path.dirname(os.path.abspath(__file__))
    SHARED_BASE_DIR = os.path.abspath(os.path.join(PROJECT_ROOT, "..", "..", "..", "tre-shared-documents"))
    TEMP_DIR = os.path.join(SHARED_BASE_DIR, "tmp")

    try:
        print("[DEBUG] Listing files in temporary directory:", TEMP_DIR)
        files = []
        for root, dirs, filenames in os.walk(TEMP_DIR):
            for filename in filenames:
                file_path = os.path.join(root, filename)
                relative_path = os.path.relpath(file_path, TEMP_DIR)
                files.append(relative_path)
        print(f"[DEBUG] Total files found: {len(files)}")
        audit_logger.info(f"GET_FILES | SUCCESS | user_id={user_id} | username={username} | IP={request.remote_addr} | files={len(files)}")
        return jsonify({"output": files}), 200
    except Exception as e:
        print(f"[ERROR] Exception in get_file: {e}")
        audit_logger.warning(f"GET_FILES | ERROR | user_id={user_id} | username={username} | IP={request.remote_addr} | error={str(e)}")
        return jsonify({"error": str(e)}), 500

    
