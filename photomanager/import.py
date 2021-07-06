"""Contains functions used to move files from the camera to a local directory.
"""
import argparse
import datetime
import pathlib
import shutil
import sys

import piexif

# The supported extensions
SUPPORTED_EXTENSIONS = {'.jpg', '.jpeg', '.orf'}


def scan_directory(input_dir: pathlib.Path):
    """Scan a directory for photo files.

    :param input_dir: The directory to scan.
    """
    for input_file in input_dir.glob("**/*"):
        if input_file.is_file() and input_file.suffix.lower() in SUPPORTED_EXTENSIONS:
            yield input_file


def import_file(input_file: pathlib.Path, output_dir: pathlib.Path):
    """Import the input file to the destination directory.

    :param input_file: The input file.
    :param output_dir: The destination directory.
    :return:
    """
    print(f"Processing file {input_file}")
    file_info = piexif.load(str(input_file))

    create_date = datetime.datetime.strptime(file_info['0th'][306].decode('ascii'), '%Y:%m:%d %H:%M:%S')
    target_directory = output_dir / f"{create_date:%Y/%m}"
    target_directory.mkdir(parents=True, exist_ok=True)
    shutil.move(input_file, target_directory / input_file.name)


def main():
    """The main entry point of the script.
    """
    # Configure the argument parser
    parser = argparse.ArgumentParser()
    parser.add_argument("input_dir", help="The input directory to scan for image files")
    parser.add_argument("output_dir", help="The output directory in which to copy files")
    args = parser.parse_args()

    # Validate that the arguments are actually directories
    input_dir = pathlib.Path(args.input_dir)
    if not input_dir.is_dir():
        sys.exit(f"{input_dir} is not a directory")
    output_dir = pathlib.Path(args.output_dir)
    if not output_dir.is_dir():
        sys.exit(f"{output_dir} is not a directory")

    for input_file in scan_directory(input_dir):
        import_file(input_file, output_dir)


if __name__ == '__main__':
    main()
