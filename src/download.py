"""
Downloads a file or folder from Google Drive given a URL to a resource that has been
shared with the Service Account used to authenticate.
"""
import io
import logging
import os.path
import re
import sys
from http import HTTPStatus
from uuid import uuid4

from google.auth.transport.requests import Request
from google.oauth2.service_account import Credentials
from googleapiclient.discovery import Resource, build
from googleapiclient.errors import HttpError
from googleapiclient.http import MediaIoBaseDownload

# Map Google Docs file-type to another MimeType, used in `service.files().export()`.
# NOTE: Items with the value `None` will not be downloaded.
#
# References:
#   https://developers.google.com/drive/api/v3/mime-types
GOOGLE_DOCS_EXPORT_TYPES = {
    # Google Docs
    "application/vnd.google-apps.document": {
        "mime_type": "application/pdf",
        "file_extension": "pdf",
    },
    # 3rd party shortcut
    "application/vnd.google-apps.drive-sdk": None,
    # Google Drawing
    "application/vnd.google-apps.drawing": {
        "mime_type": "image/png",
        "file_extension": "png",
    },
    # Google Drive file
    "application/vnd.google-apps.file": None,
    # Google Drive folder
    "application/vnd.google-apps.folder": None,
    # Google Forms
    "application/vnd.google-apps.form": None,
    # Google Fusion Tables
    "application/vnd.google-apps.fusiontable": None,
    # Google My Maps
    "application/vnd.google-apps.map": None,
    # Google Slides
    "application/vnd.google-apps.presentation": {
        "mime_type": "application/pdf",
        "file_extension": "pdf",
    },
    # Google Apps Scripts
    "application/vnd.google-apps.script": None,
    # Shortcut
    "application/vnd.google-apps.shortcut": None,
    # Google Sites
    "application/vnd.google-apps.site": None,
    # Google Sheets
    "application/vnd.google-apps.spreadsheet": {
        "mime_type": "application/pdf",
        "file_extension": "pdf",
    },
    # Other
    "application/vnd.google-apps.audio": {
        "mime_type": "audio/webm",
        "file_extension": "webm",
    },
    "application/vnd.google-apps.photo": {
        "mime_type": "image/webp",
        "file_extension": "webp",
    },
    "application/vnd.google-apps.video": {
        "mime_type": "video/webm",
        "file_extension": "webm",
    },
    "application/vnd.google-apps.unknown": None,
}
GOOGLE_DRIVE_FOLDER = "application/vnd.google-apps.folder"

# NOTE: If modifying these scopes, delete the file token.json.
SCOPES = [
    "https://www.googleapis.com/auth/drive.metadata.readonly",
    "https://www.googleapis.com/auth/drive.readonly",
]


# Settings
DOWNLOAD_CHUNK_SIZE = 1024 * 1024
DOWNLOAD_CHUNK_RETRIES = 2
FOLDER_ITEMS_PAGE_SIZE = 300
DESTINATION_ROOT = "./buffer_folder"
ERROR_REPORT_FILENAME = "google_drive_download_error_report.log"
# Logging settings
logging.basicConfig(level="INFO")
logging.getLogger("google_auth_httplib2").setLevel(logging.CRITICAL)
logging.getLogger("googleapiclient").setLevel(logging.CRITICAL)
# Get root logger
LOGGER = logging.getLogger()


def _encode_path_safe_filename(filename: str):
    """
    Returns a path-safe for the given filename, replacing invalid chars as "/"
    """
    return filename.replace("/", "_")


def _extract_google_drive_id_from_url(url: str):
    match = re.search(r"[-\w]{25,}", url)
    if match:
        return match.group()

    raise Exception('Could not extract ID from url "%s"')


def _get_google_drive_service(creds: Credentials = None) -> Resource:
    """
    Authenticate a service account and returns a Resource instance,
    for the Google Drive API v3 service.
    """

    LOGGER.info("Authenticating GCP Service-Account...")

    # If there are no credentials available, let the user log in.
    if creds is None:
        LOGGER.debug("Authenticating using credentials file...")
        credential_candidates = [
            entry.path
            for entry in os.scandir("credential")
            if entry.name.endswith(".json")
        ]
        if not credential_candidates:
            LOGGER.error("Missing credentials file!")
            return None

        credential_json_path = credential_candidates[0]
        creds = Credentials.from_service_account_file(
            credential_json_path, scopes=SCOPES
        )
        LOGGER.debug("Authenticating using credentials file...Done")

    elif creds.expired:
        LOGGER.debug("Expired token, refreshing...")
        creds.refresh(Request())
        LOGGER.debug("Expired token, refreshing...Done")

    LOGGER.debug("Starting Google Drive service...")
    service = build("drive", "v3", credentials=creds)
    LOGGER.info("Starting Google Drive service...Done")

    return service


def _download_folder(service: Resource, item_id: str, full_path: str):
    LOGGER.info("Stepping into folder: %s", full_path)

    # Make sure the path exists
    if not os.path.isdir(full_path):
        os.mkdir(path=full_path)

    LOGGER.debug("Retrieving folder content list (%s)...", item_id)
    results = (
        service.files()
        .list(
            pageSize=FOLDER_ITEMS_PAGE_SIZE,
            q=f'parents in "{item_id}"',
            fields="files(id, name, mimeType)",
            includeItemsFromAllDrives=True,
            corpora="allDrives",
            supportsAllDrives=True,
        )
        .execute()
    )

    items = results.get("files", [])

    if not items:
        LOGGER.info("Retrieving folder content list (%s)...Empty folder", item_id)
        return

    LOGGER.debug(
        "Retrieving folder content list (%s)...Done! %d items", item_id, len(items)
    )

    for item in items:
        _download_item(service=service, item=item, dst_path=full_path)


def _download_into_file(request, full_path, item_id, item_name):
    file_handler = io.FileIO(full_path, mode="wb")
    try:
        downloader = MediaIoBaseDownload(
            file_handler, request, chunksize=DOWNLOAD_CHUNK_SIZE
        )

        done = False
        while not done:
            status, done = downloader.next_chunk(num_retries=DOWNLOAD_CHUNK_RETRIES)
            if status:
                LOGGER.debug(
                    'Downloading (%s) "%s"...%d%%.',
                    item_id,
                    item_name,
                    int(status.progress() * 100),
                )
        LOGGER.info('Downloading (%s) "%s"...Complete!', item_id, item_name)
    finally:
        file_handler.close()


def _download_file(
    service: Resource, item_id: str, item_name: str, mime_type: str, full_path: str
):
    LOGGER.debug(
        'Downloading (%s) "%s"... Type="%s" Path="%s"',
        item_id,
        item_name,
        mime_type,
        full_path,
    )

    try:
        if mime_type not in GOOGLE_DOCS_EXPORT_TYPES:
            request = service.files().get_media(fileId=item_id, supportsAllDrives=True)

        else:
            # Google Doc files need to be exported
            # NOTE: The exported content is limited to 10MB

            export_settings = GOOGLE_DOCS_EXPORT_TYPES[mime_type]
            file_extension = export_settings["file_extension"]
            exported_mime_type = export_settings["mime_type"]

            LOGGER.debug(
                'Downloading (%s) "%s"...Type="%s" will be exported as "%s"',
                item_id,
                item_name,
                mime_type,
                exported_mime_type,
            )

            # append file extension
            full_path = f"{full_path}.{file_extension}"
            request = service.files().export_media(
                fileId=item_id, mimeType=exported_mime_type
            )

        # The actual download
        _download_into_file(
            request=request, full_path=full_path, item_id=item_id, item_name=item_name
        )

    except HttpError as err:
        # Try to extract the error message from the exception
        try:
            error_message = err.error_details[0]["message"]
        # Defaults to the exception string
        except (AttributeError, IndexError, KeyError):
            error_message = str(err)

        # Append user guidance on http 403
        if err.status_code == HTTPStatus.FORBIDDEN:
            error_message += (
                " If you think this is a mistake, please check if the file is"
                " configured to allow downloads from viewers before reporting."
            )

        LOGGER.error(
            'Downloading (%s) "%s"...Failed. %s', item_id, item_name, error_message
        )

        # Write an error report in the folder, to enhance the error management
        folder = os.path.dirname(full_path)
        with open(os.path.join(folder, ERROR_REPORT_FILENAME), "a+") as fp_error_report:
            fp_error_report.write(
                f'Failed to download ({item_id}) "{item_name}": {error_message}\n'
            )

        # Remove empty file left behind
        if os.path.getsize(full_path) == 0:
            os.remove(full_path)

            LOGGER.debug(
                'Downloading (%s) "%s"...Failed. The empty file at %s was removed.',
                item_id,
                item_name,
                full_path,
            )


def _download_item(service: Resource, item: dict, dst_path: str):
    """
    Download a file into the given path

    Args:
        service:
    """
    item_id = item["id"]
    item_name = item["name"]
    mime_type = item["mimeType"]

    # Note: The parent folders in dst_path must exist
    full_path = os.path.join(dst_path, _encode_path_safe_filename(item_name))

    # Protect existing files by appending a uuid to the new one
    if os.path.exists(full_path):
        suffix = f"-{uuid4()}"
        LOGGER.warning(
            (
                'Path conflict (%s): There was already a "%s" at "%s",'
                ' "%s" will be appended to the name.'
            ),
            item_id,
            item_name,
            dst_path,
            suffix,
        )
        full_path += suffix

    if mime_type == GOOGLE_DRIVE_FOLDER:
        # Recursive step
        _download_folder(service=service, item_id=item_id, full_path=full_path)
    else:
        _download_file(
            service=service,
            item_id=item_id,
            item_name=item_name,
            mime_type=mime_type,
            full_path=full_path,
        )


def download_from_google_drive(google_drive_url: str) -> None:
    """
    Download a file or every file in a folder pre-shared with the service account.

    Raises:
        HttpError
    """
    google_drive_id = _extract_google_drive_id_from_url(google_drive_url)

    service = _get_google_drive_service()
    if service is None:
        LOGGER.error("Failed to authenticate!")
        return

    # Check access to folder
    LOGGER.info("Trying to access item (%s)...", google_drive_id)
    try:
        item: dict = (
            service.files()
            .get(fileId=google_drive_id, supportsAllDrives=True)
            .execute()
        )

        item_type = "folder" if item["mimeType"] == GOOGLE_DRIVE_FOLDER else "file"
        LOGGER.info(
            "Trying to access item (%s)...Done! It is a %s", google_drive_id, item_type
        )
        LOGGER.debug("Trying to access item (%s)...Done! %r", google_drive_id, item)

    except HttpError as err:
        if err.status_code == HTTPStatus.NOT_FOUND:
            LOGGER.error(
                (
                    "Trying to access item...Failed!"
                    ' ID="%s" was not found.'
                    " Make sure it has been shared with the service account."
                ),
                google_drive_id,
            )
            return

        # Raise if any other thing has happened
        raise

    # Make sure root folder exists
    path = os.path.join(DESTINATION_ROOT, str(uuid4()))
    if not os.path.isdir(path):
        os.mkdir(path=path)

    LOGGER.info("Downloading Google Drive files into %s...", path)
    try:
        _download_item(service=service, item=item, dst_path=path)
    except HttpError as err:
        # Try to extract the error message from the exception
        try:
            error_message = err.error_details[0]["message"]
        # Defaults to the exception string
        except (AttributeError, IndexError, KeyError):
            error_message = str(err)
        LOGGER.error(
            "Downloading Google Drive files into %s...Failed! %s", path, error_message
        )
        return
    LOGGER.info("Downloading Google Drive files into %s...Complete!", path)


if __name__ == "__main__":
    try:
        if len(sys.argv) != 2:
            LOGGER.error('Usage: python download.py "GOOGLE DRIVE RESOURCE URL"')
        else:
            GOOGLE_DRIVE_URL = str(sys.argv[1])
            download_from_google_drive(google_drive_url=GOOGLE_DRIVE_URL)
    except KeyboardInterrupt:
        LOGGER.warning("User interrupted via keyboard.")
