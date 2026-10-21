import datetime
import logging
import os
import re
import threading
import time
from zoneinfo import ZoneInfo

from flask import Flask, abort, render_template, request, send_from_directory

app = Flask(__name__)
logger = logging.getLogger(__name__)

BACKUP_ROOTS = {
    'Brocade': '/mnt/brocade/backups',
    'Juniper': '/mnt/juniper/backups',
    'Datacom': '/mnt/datacom/backups',
    'Fortinet': '/mnt/fortinet/backups',
}
MANAUS = ZoneInfo('America/Manaus')


def positive_int_env(name, default):
    try:
        value = int(os.getenv(name, str(default)))
        return value if value > 0 else default
    except ValueError:
        logger.warning('Valor inválido para %s; usando %s', name, default)
        return default


CACHE_SECONDS = positive_int_env('BACKUP_CACHE_SECONDS', 60)
STALE_HOURS = positive_int_env('BACKUP_STALE_HOURS', 24)
_cache_lock = threading.Lock()
_cache_data = None
_cache_expires = 0


def format_date(timestamp):
    return datetime.datetime.fromtimestamp(timestamp, MANAUS).strftime('%d/%m/%Y %H:%M')


def format_size(size):
    for unit in ('B', 'KB', 'MB', 'GB'):
        if size < 1024 or unit == 'GB':
            return f'{size:.1f} {unit}'
        size /= 1024


def scan_file(entry, device_name, in_subfolder):
    try:
        # Links can point outside a read-only backup mount; do not list them.
        if entry.is_symlink() or not entry.is_file(follow_symlinks=False):
            return None
        stat = entry.stat(follow_symlinks=False)
    except OSError as exc:
        logger.warning('Não foi possível ler o backup %s: %s', entry.path, exc)
        return None

    display_name = entry.name
    if entry.name.startswith(device_name):
        display_name = entry.name[len(device_name):].lstrip('_- ') or entry.name
    return {
        'filename': entry.name,
        'display_name': display_name,
        'date': format_date(stat.st_mtime),
        'timestamp': stat.st_mtime,
        'size': format_size(stat.st_size),
        'is_in_subfolder': in_subfolder,
    }


def get_data_structure():
    data = {'vendors': {}}
    stale_before = time.time() - STALE_HOURS * 3600

    for vendor, root_dir in BACKUP_ROOTS.items():
        vendor_data = {'devices': {}, 'device_count': 0, 'backup_count': 0,
                       'last_update': 'N/A', 'available': True}
        latest_timestamp = 0
        try:
            with os.scandir(root_dir) as entries:
                root_items = sorted(entries, key=lambda entry: entry.name)
        except OSError as exc:
            logger.warning('Diretório de %s indisponível (%s): %s', vendor, root_dir, exc)
            vendor_data['available'] = False
            data['vendors'][vendor] = vendor_data
            continue

        for item in root_items:
            if item.name.startswith('.'):
                continue
            try:
                if item.is_symlink():
                    continue
                if item.is_dir(follow_symlinks=False):
                    device_name = item.name
                    files = []
                    try:
                        with os.scandir(item.path) as entries:
                            device_items = sorted(entries, key=lambda entry: entry.name, reverse=True)
                    except OSError as exc:
                        logger.warning('Equipamento %s/%s indisponível: %s', vendor, device_name, exc)
                        vendor_data['devices'][device_name] = {
                            'files': [], 'last_update': 'N/A', 'status': 'indisponivel'
                        }
                        continue
                    for entry in device_items:
                        if not entry.name.startswith('.'):
                            backup = scan_file(entry, device_name, True)
                            if backup:
                                files.append(backup)
                elif item.is_file(follow_symlinks=False):
                    match = re.search(r'^(.*?)_?\d{8}_\d{6}', item.name)
                    device_name = match.group(1).rstrip('_') if match else 'Geral'
                    backup = scan_file(item, device_name, False)
                    if not backup:
                        continue
                    files = [backup]
                else:
                    continue
            except OSError as exc:
                logger.warning('Item %s indisponível: %s', item.path, exc)
                continue

            device = vendor_data['devices'].setdefault(
                device_name, {'files': [], 'last_update': 'N/A', 'status': 'ausente'}
            )
            device['files'].extend(files)

        for device in vendor_data['devices'].values():
            device['files'].sort(key=lambda backup: backup['timestamp'], reverse=True)
            vendor_data['backup_count'] += len(device['files'])
            if device['status'] == 'indisponivel' or not device['files']:
                continue
            timestamp = device['files'][0]['timestamp']
            device['last_update'] = format_date(timestamp)
            device['status'] = 'atrasado' if timestamp < stale_before else 'em_dia'
            latest_timestamp = max(latest_timestamp, timestamp)

        vendor_data['device_count'] = len(vendor_data['devices'])
        if latest_timestamp:
            vendor_data['last_update'] = format_date(latest_timestamp)
        data['vendors'][vendor] = vendor_data
    return data


def get_cached_data(force=False):
    global _cache_data, _cache_expires
    with _cache_lock:
        if force or _cache_data is None or time.monotonic() >= _cache_expires:
            _cache_data = get_data_structure()
            _cache_expires = time.monotonic() + CACHE_SECONDS
        return _cache_data


@app.route('/')
def index():
    view_data = get_cached_data(force=request.args.get('refresh') == '1')
    vendor_name = request.args.get('vendor')
    device_name = request.args.get('device')
    current_vendor_data = view_data['vendors'].get(vendor_name)
    current_device_data = None
    if current_vendor_data and device_name:
        current_device_data = current_vendor_data['devices'].get(device_name)
    if vendor_name and current_vendor_data is None:
        abort(404)
    if device_name and current_device_data is None:
        abort(404)
    return render_template('index.html', data=view_data, current_vendor=vendor_name,
                           vendor_data=current_vendor_data, current_device=device_name,
                           device_data=current_device_data, stale_hours=STALE_HOURS)


@app.route('/download/<vendor>/<device>/<filename>')
def download_file(vendor, device, filename):
    root = BACKUP_ROOTS.get(vendor)
    if root is None:
        abort(404)
    device_data = get_cached_data()['vendors'][vendor]['devices'].get(device)
    if not device_data:
        abort(404)
    backup = next((item for item in device_data['files'] if item['filename'] == filename), None)
    if backup is None:
        abort(404)

    directory = os.path.join(root, device) if backup['is_in_subfolder'] else root
    try:
        # Revalidate after the inventory scan: a file may have been removed or replaced.
        root_real = os.path.realpath(root)
        directory_real = os.path.realpath(directory)
        file_path = os.path.join(directory, filename)
        if os.path.commonpath((root_real, directory_real)) != root_real:
            abort(404)
        if os.path.islink(directory) or os.path.islink(file_path) or not os.path.isfile(file_path):
            abort(404)
        if os.path.commonpath((root_real, os.path.realpath(file_path))) != root_real:
            abort(404)
        return send_from_directory(directory, filename, as_attachment=True)
    except OSError as exc:
        logger.warning('Download indisponível: %s: %s', filename, exc)
        abort(404)


if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000)
