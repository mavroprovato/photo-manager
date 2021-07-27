import argparse
import json
import logging
import pathlib
import sys

from google_auth_oauthlib.flow import InstalledAppFlow
import requests

CONFIG_DIR = pathlib.Path(__file__).resolve().parent.parent
TOKENS_FILE = CONFIG_DIR / 'tokens.json'
CREDENTIALS_FILE = CONFIG_DIR / 'credentials.json'

logger = logging.getLogger(__name__)


class GooglePhotos:
    """Manage communication with the Google Photos API.
    """

    def __init__(self):
        """Create the object.
        """
        self.client_config = self._load_client_config()
        self.tokens = self._load_tokens()
        self.media_items = self._load_media_items()

    @staticmethod
    def _load_client_config() -> dict:
        """Load the client configuration.

        :return: The client configuration.
        """
        logger.debug("Loading the client configuration")
        with open(CREDENTIALS_FILE, "r") as json_file:
            return json.load(json_file)

    @staticmethod
    def _load_tokens() -> dict:
        """Load the tokens.

        :return: The tokens.
        """
        logger.debug("Loading the tokens")
        # Try to get the tokens from file
        if TOKENS_FILE.is_file():
            try:
                with TOKENS_FILE.open('r') as f:
                    return json.load(f)
            except Exception as ex:
                logger.warning("Could not read credentials file", exc_info=ex)

        # Launch the OAuth Flow and save credentials
        logger.info("Tokens not found, launching the OAuth flow")
        flow = InstalledAppFlow.from_client_secrets_file(
            client_secrets_file=str(CREDENTIALS_FILE), scopes=['https://www.googleapis.com/auth/photoslibrary'])
        flow.run_local_server(port=8080)
        tokens = {'token': flow.credentials.token, 'refresh_token': flow.credentials.refresh_token}
        with TOKENS_FILE.open('w') as f:
            json.dump(tokens, f)

        return tokens

    def _make_request(self, method: str, url: str, **kwargs):
        """Make a request to the Google Photos API.

        :param url: The url.
        :param params: The parameters.
        :return: The response.
        """
        logger.debug("Making %s request to url %s ", method, url)
        response = requests.request(
            method=method, url=url, **kwargs, headers={'Authorization': f"Bearer {self.tokens['token']}"})
        if response.status_code == 401:
            self._refresh_token()

            response = requests.request(
                method=method, url=url, **kwargs, headers={'Authorization': f"Bearer {self.tokens['token']}"})
            response.raise_for_status()

        return response

    def _refresh_token(self):
        """Refresh the token.
        """
        logger.debug("Refreshing the token")
        response = requests.post(
            url='https://oauth2.googleapis.com/token',
            params={
                'client_id': self.client_config['installed']['client_id'],
                'client_secret': self.client_config['installed']['client_secret'],
                'grant_type': 'refresh_token',
                'refresh_token': self.tokens['refresh_token']
            }
        )
        self.tokens['token'] = response.json()['access_token']
        with TOKENS_FILE.open('w') as f:
            json.dump(self.tokens, f)

    def _load_media_items(self):
        """Load the media items.

        :return: The media items.
        """
        logger.info("Loading media items")
        media_items = []
        page_token = None
        while True:
            response = self._make_request(method='GET', url='https://photoslibrary.googleapis.com/v1/mediaItems',
                                          params={'pageSize': 100, 'pageToken': page_token})
            media_items += response.json()['mediaItems']
            page_token = response.json().get('nextPageToken')
            if not page_token:
                break

        logger.info("Media items loaded")

        return media_items

    def upload_missing(self, path: pathlib.Path):
        file_names = {media_item['filename'] for media_item in self.media_items}
        for path in path.glob('**/*.JPG'):
            if path.name not in file_names:
                logger.info("Uploading file %s", path)
                with path.open('rb') as f:
                    data = f.read()
                    response = self._make_request(
                        method='POST', url='https://photoslibrary.googleapis.com/v1/uploads', data=data
                    )
                    response.raise_for_status()
                    logger.info("File %s uploaded, adding to library", path)
                    upload_token = response.text
                    self._make_request(
                        method='POST', url='https://photoslibrary.googleapis.com/v1/mediaItems:batchCreate',
                        json={
                            'newMediaItems': [
                                {
                                    "simpleMediaItem": {
                                        "fileName": str(path.name),
                                        "uploadToken": upload_token
                                    }
                                }
                            ]
                        }
                    )
                    logger.info("File %s uploaded, added to library", path)


def main():
    gp = GooglePhotos()
    logger.info("%s files in library", len(gp.media_items))

    parser = argparse.ArgumentParser(description='Upload files to Google photos')
    parser.add_argument('input_path', help='the input file path')
    args = parser.parse_args()
    path = pathlib.Path(args.input_path)
    if not path.is_dir():
        logger.error("Path %s does not exist or is not a directory", path)
    gp.upload_missing(path)


if __name__ == '__main__':
    logging.basicConfig(stream=sys.stdout, level=logging.INFO)
    main()
