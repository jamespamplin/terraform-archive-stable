import base64
import fnmatch
import hashlib
import json
import os
import stat
import sys
import tempfile
import zipfile

query = json.load(sys.stdin)
search = json.loads(query["search"])
source_dir = query["source_dir"]
output_path = query["output_path"]

source_files = {}
search_results = []
for root, dirs, files in os.walk(source_dir):
    for name in dirs + files:
        path = os.path.join(root, name)
        relative_path = os.path.relpath(path, source_dir)
        source_files[relative_path] = path
        for pattern in search:
            if fnmatch.fnmatch(relative_path, pattern):
                search_results.append(relative_path)

temp_file = tempfile.NamedTemporaryFile(delete=False)
try:

    with zipfile.ZipFile(temp_file.name, "w", zipfile.ZIP_DEFLATED) as zip_file:
        for relative_path, absolute_path in sorted(source_files.items()):

            # Get file/directory details.
            st = os.stat(absolute_path)
            is_dir = stat.S_ISDIR(st.st_mode)
            if is_dir:
                relative_path += "/"

            info = zipfile.ZipInfo(relative_path)

            # Set all dates the same.
            date_time = (1980, 1, 1, 0, 0, 0)
            info.date_time = date_time

            # Set permissions to 755 or 644.
            if st.st_mode & stat.S_IXUSR:
                mode = 0o755
            else:
                mode = 0o644
            info.external_attr = (stat.S_IFREG | mode) << 16

            # Read the file contents.
            if is_dir:
                contents = b""
                size = 0
            else:
                with open(absolute_path, "rb") as open_file:
                    contents = open_file.read()
                size = len(contents)

            # Add the file to the zip.
            zip_file.writestr(info, contents)

    output_md5 = hashlib.md5()
    output_sha = hashlib.sha1()
    output_sha256 = hashlib.sha256()

    temp_file.seek(0)
    while True:
        data = temp_file.read(65536)  # 64kb
        if data:
            output_md5.update(data)
            output_sha.update(data)
            output_sha256.update(data)
        else:
            break

    os.rename(temp_file.name, output_path)

except Exception:
    os.remove(temp_file)
    raise

json.dump(
    {
        "output_base64sha256": base64.b64encode(output_sha256.digest()).decode(),
        "output_md5": output_md5.hexdigest(),
        "output_path": output_path,
        "output_sha": output_sha.hexdigest(),
        "search": json.dumps(search),
        "search_results": json.dumps(sorted(search_results)),
        "source_dir": source_dir,
    },
    sys.stdout,
    indent=2,
)
