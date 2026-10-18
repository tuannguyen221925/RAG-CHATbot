"""Private avatar storage; decode and resize away from the event loop."""
import io
import warnings
from urllib.parse import quote

from PIL import Image, ImageOps
from starlette.concurrency import run_in_threadpool

from .security import AppError, digest, safe_user

PRESETS = {'default', 'robot', 'fox', 'cat', 'panda', 'flower', 'leaf', 'moon', 'planet', 'rocket'}


def metadata(row, slot):
    if not row:
        return {'preset': 'default'}
    result = {'preset': row['preset']}
    if row.get('sha256'):
        result['url'] = f"/api/avatars/{quote(slot, safe='')}/image?v={row['sha256']}"
    return result


async def user_with_avatar(db, user):
    rows = await db.query('SELECT preset,sha256 FROM avatars WHERE user_id=%s AND slot=%s', (user['id'], 'profile'))
    return safe_user(user) | {'avatar': metadata(rows[0] if rows else None, 'profile')}


async def set_avatar(db, user_id, slot, preset):
    if not isinstance(preset, str) or preset not in PRESETS:
        raise AppError('Chọn một avatar được hỗ trợ.')
    await db.query('INSERT INTO avatars(user_id,slot,preset) VALUES (%s,%s,%s) ON DUPLICATE KEY UPDATE preset=VALUES(preset),file_blob=NULL,sha256=NULL', (user_id, slot, preset))
    return {'preset': preset}


def resize_image(content):
    try:
        with warnings.catch_warnings():
            warnings.simplefilter('error', Image.DecompressionBombWarning)
            with Image.open(io.BytesIO(content)) as image:
                if image.format not in ('JPEG', 'PNG', 'WEBP') or getattr(image, 'n_frames', 1) != 1 or image.width * image.height > 20_000_000:
                    raise ValueError('Unsupported image')
                image.load()
                fitted = ImageOps.fit(ImageOps.exif_transpose(image).convert('RGB'), (384, 384), method=Image.Resampling.LANCZOS)
                output = io.BytesIO()
                fitted.save(output, format='JPEG', quality=88)
                return output.getvalue()
    except Exception as exc:
        raise AppError('Ảnh không hợp lệ. Chọn JPG, PNG hoặc WebP tĩnh, tối đa 20 triệu pixel.') from exc


async def upload_avatar(db, user_id, slot, upload):
    if upload is None or not hasattr(upload, 'read'):
        raise AppError('Chọn một ảnh JPG, PNG hoặc WebP.')
    content = await upload.read(5 * 1024 * 1024 + 1)
    if len(content) > 5 * 1024 * 1024:
        raise AppError('Ảnh vượt giới hạn tải lên (tối đa 5 MB, một ảnh).')
    if not content:
        raise AppError('Chọn một ảnh JPG, PNG hoặc WebP.')
    buffer = await run_in_threadpool(resize_image, content)
    sha = digest(buffer)
    await db.query("INSERT INTO avatars(user_id,slot,preset,file_blob,sha256) VALUES (%s,%s,'custom',%s,%s) ON DUPLICATE KEY UPDATE preset='custom',file_blob=VALUES(file_blob),sha256=VALUES(sha256)", (user_id, slot, buffer, sha))
    return metadata({'preset': 'custom', 'sha256': sha}, slot)
