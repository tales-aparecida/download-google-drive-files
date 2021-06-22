[![License: MIT](https://img.shields.io/badge/License-MIT-informational)](https://github.com/tales-aparecida/dump-google-drive/blob/main/LICENSE)
![Python >= 3.6](https://img.shields.io/badge/Python-≥3.6-informational.svg)
[![Code style: black](https://img.shields.io/badge/Code%20Style-Black-000000.svg)](https://github.com/psf/black)

# dump-google-drive

A small script to download a file or a whole folder from Google Drive.

---

## Installation and usage

### Installation

This project requires Python ≥ 3.6 and we strongly recommend that you use a [virtual environment](https://docs.python.org/3/library/venv.html) before installing the dependencies via `pip` with:

```
pip install -r requirements.txt
```

### Acquiring a GCP Service Account credential file

In order to run this script you will need a JSON file with the credentials for a service account, which technically will be the one downloading the files.
Note that you might need administration rights to do this.

First, you will need a GCP project, so if you don't have one yet, create a new one at the [GCP Resource Manager](https://console.developers.google.com/project).

<img alt="Create a project at Google Cloud Platform" src="docs/readme-create-project.png"/>

Next, you need to enable the [Google Drive API](https://console.cloud.google.com/marketplace/product/google/drive.googleapis.com) at the [GCP MarketPlace](https://console.cloud.google.com/marketplace/), by just opening the "Google Drive API" page and clicking in the "Enable" button.

<img alt="Click in the 'Enable' button in the 'Google Drive API' page" src="docs/readme-google-drive-api.png"/>

Now, go to the [credentials page](https://console.cloud.google.com/apis/credentials) and **create a service account** by clicking in the "Create Credentials" button, choosing "Service account" and filling the form.

Then, go to the ["Manage service accounts"](https://console.cloud.google.com/iam-admin/serviceaccounts) page, in the "Service accounts" table, click in the "actions" link for the new service account row, and choose the "Manage keys" option. This can also be achieved by going to the "Edit service account page". In the key management page, **create a new key**, choose JSON if prompted.

<img alt="Create a service account, then create and download a new key" src="docs/readme-create-credentials.png"/>

This will download the credentials file that will be used by the script, HANDLE THIS FILE WITH CARE, as it can give access to your files. The file contents will be structured like so:

```json
{
    "type": "service_account",
    "project_id": "api-project-XXX",
    "private_key_id": "2cd … ba4",
    "private_key": "-----BEGIN PRIVATE KEY-----\nNrLw … jIh/9\n-----END PRIVATE KEY-----\n",
    "client_email": "473000000000-yoursisdifferent@developer.gserviceaccount.com",
    "client_id": "473 … hd.apps.googleusercontent.com",
    ...
}
```

---

### Download a file or a folder

First, **share the desired resource**, file or folder, with the service account. You can see its email address in the Google console or in the downloaded credential file, under the "client_email" key.

Now copy the resource URL and pass it to the `download_from_google_drive()` function, or run the script with:

```sh
$ python download.py "GOOGLE DRIVE RESOURCE URL"
```

The URL should look a bit like "https://drive.google.com/drive/folders/2KRQwhxUpJl-JfRFNu94telK0635Kz4Hd?usp=sharing". The random characters are the resource ID, which will actually be used to find and download it.

---

## How to contribute

This project uses [Black](https://github.com/psf/black) as code style and autoformatter, along with the linters [Flake8](https://github.com/PyCQA/flake8) and [Pylint](https://github.com/PyCQA/pylint/). They will be enforced when you try to commit via `git hooks`.

We try to follow the [Google Style Python Docstrings](https://sphinxcontrib-napoleon.readthedocs.io/en/latest/example_google.html), but they will not be **automatically** enforced. However, if the reviewers _suggest_ that it could enhance the code quality, try to comply.

Finally, the code should be readable by itself, but do **add comments above non trivial lines** and blocks to ease the reader into the semantic value of your code.

### Install dependencies

Install development requirements to enable linting and autoformatting.

```
$ pip install -r requirements_dev.txt
```

### Setup git hooks with pre-commit

Run `pre-commit install` to set up the _git hooks_, which will make sure that every code that you commit will comply to the _enforced code style rules_. Which means that every time you try to commit something, the autoformatter will fix any mistakes and **you will need to _stage_ those offending files again**.

```
$ pre-commit install
pre-commit installed at .git/hooks/pre-commit
```

### Suggested editor configs

#### VScode

```json
{
  "editor.formatOnSave": true,
  "editor.codeActionsOnSave": {
    "source.organizeImports": true,
    "source.fixAll": true
  },

  "python.formatting.provider": "black",
  "python.linting.pylintEnabled": true,
  "python.linting.flake8Enabled": true
}
```

---

## References used while writing the script

### About authentication and downloading files

https://stackoverflow.com/questions/39003409/how-to-download-specific-google-drive-folder-using-python
https://developers.google.com/drive/api/v3/quickstart/python
https://developers.google.com/drive/api/v3/manage-downloads
https://developers.google.com/drive/api/v3/reference/files/export
https://developers.google.com/drive/api/v3/reference/files/get

### About MimeTypes

https://developers.google.com/drive/api/v3/mime-types
https://developer.mozilla.org/en-US/docs/Web/HTTP/Basics_of_HTTP/MIME_types
