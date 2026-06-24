#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""上传本地文件到阿里云 OSS（V1 签名，纯标准库，零依赖）。

环境变量：
  OSS_ACCESS_KEY_ID      必填，RAM AccessKey ID（强烈建议用子账号 + 最小权限）
  OSS_ACCESS_KEY_SECRET  必填，RAM AccessKey Secret
  OSS_BUCKET             必填，Bucket 名
  OSS_ENDPOINT           必填，地域域名，如 oss-cn-hangzhou.aliyuncs.com
  OSS_DOMAIN             可选，绑定的自定义域名 / CDN；不填用 Bucket 默认域名
  OSS_PREFIX             可选，对象前缀，如 elibot/articles

用法：
  python upload_oss.py <本地文件> <对象名（不含前缀，会自动拼接 OSS_PREFIX）>
标准输出最后一行为公开 URL。
退出码：0 成功；1 参数错；2 环境变量缺失；3 上传失败。
"""
import os
import sys
import hmac
import hashlib
import base64
import urllib.request
import urllib.error
from email.utils import formatdate


def load_env_file():
    """从 skill 内 config/oss.env 加载 OSS 凭证（仅当环境变量未设时；命令行/系统环境优先）。"""
    config = os.path.join(os.path.dirname(os.path.abspath(__file__)), '..', 'config', 'oss.env')
    if not os.path.exists(config):
        return
    with open(config, encoding='utf-8') as f:
        for line in f:
            line = line.strip()
            if not line or line.startswith('#'):
                continue
            if line.startswith('export '):
                line = line[len('export '):]
            if '=' in line:
                k, _, v = line.partition('=')
                k = k.strip()
                v = v.strip().strip('"').strip("'")
                if k and k not in os.environ:
                    os.environ[k] = v

# 解决 Windows GBK 控制台输出中文报错
try:
    sys.stdout.reconfigure(encoding='utf-8', errors='replace')
    sys.stderr.reconfigure(encoding='utf-8', errors='replace')
except Exception:
    pass

CONTENT_TYPES = {
    '.png': 'image/png',
    '.jpg': 'image/jpeg',
    '.jpeg': 'image/jpeg',
    '.gif': 'image/gif',
    '.webp': 'image/webp',
    '.svg': 'image/svg+xml',
}


def get_content_type(path):
    ext = os.path.splitext(path)[1].lower()
    return CONTENT_TYPES.get(ext, 'application/octet-stream')


def sign(key_secret, string_to_sign):
    digest = hmac.new(
        key_secret.encode('utf-8'),
        string_to_sign.encode('utf-8'),
        hashlib.sha1,
    ).digest()
    return base64.b64encode(digest).decode('ascii')


def upload(local_path, object_name):
    load_env_file()
    access_id = os.environ.get('OSS_ACCESS_KEY_ID', '').strip()
    access_secret = os.environ.get('OSS_ACCESS_KEY_SECRET', '').strip()
    bucket = os.environ.get('OSS_BUCKET', '').strip()
    endpoint = os.environ.get('OSS_ENDPOINT', '').strip().lstrip('/')
    domain = os.environ.get('OSS_DOMAIN', '').strip().rstrip('/')
    prefix = os.environ.get('OSS_PREFIX', '').strip().strip('/')

    missing = []
    for k, v in [
        ('OSS_ACCESS_KEY_ID', access_id),
        ('OSS_ACCESS_KEY_SECRET', access_secret),
        ('OSS_BUCKET', bucket),
        ('OSS_ENDPOINT', endpoint),
    ]:
        if not v:
            missing.append(k)
    if missing:
        print('错误：缺少 OSS 环境变量：' + ', '.join(missing), file=sys.stderr)
        return 2

    if not os.path.exists(local_path):
        print('错误：本地文件不存在：' + local_path, file=sys.stderr)
        return 1

    object_key = (prefix + '/' + object_name) if prefix else object_name

    with open(local_path, 'rb') as f:
        data = f.read()
    content_type = get_content_type(local_path)
    # 用 formatdate 避免 Windows 中文 locale 导致星期/月份非英文
    date = formatdate(usegmt=True)

    # OSS V1 签名：HTTP-Verb + \n + Content-MD5 + \n + Content-Type + \n + Date + \n + CanonicalizedResource
    resource = '/' + bucket + '/' + object_key
    string_to_sign = 'PUT\n\n' + content_type + '\n' + date + '\n' + resource
    signature = sign(access_secret, string_to_sign)

    url = 'https://' + bucket + '.' + endpoint + '/' + object_key
    req = urllib.request.Request(url, data=data, method='PUT')
    req.add_header('Content-Type', content_type)
    req.add_header('Date', date)
    req.add_header('Authorization', 'OSS ' + access_id + ':' + signature)

    try:
        with urllib.request.urlopen(req, timeout=60) as resp:
            if 200 <= resp.status < 300:
                public_url = ('https://' + domain + '/' + object_key) if domain else url
                print(public_url)
                return 0
            print('错误：OSS 上传失败，HTTP ' + str(resp.status), file=sys.stderr)
            return 3
    except urllib.error.HTTPError as e:
        body = e.read().decode('utf-8', errors='replace')
        print('错误：OSS HTTP ' + str(e.code), file=sys.stderr)
        print(body, file=sys.stderr)
        if 'SignatureDoesNotMatch' in body:
            print('提示：签名不匹配，检查 OSS_ACCESS_KEY_SECRET 是否正确', file=sys.stderr)
        elif e.code == 403 or 'AccessDenied' in body:
            print('提示：权限拒绝，检查 RAM 子账号是否有该 Bucket 的 oss:PutObject 权限', file=sys.stderr)
        elif 'NoSuchBucket' in body:
            print('提示：Bucket 不存在，检查 OSS_BUCKET 与 OSS_ENDPOINT（地域）是否匹配', file=sys.stderr)
        return 3
    except Exception as e:
        print('错误：上传异常 - ' + str(e), file=sys.stderr)
        return 3


if __name__ == '__main__':
    if len(sys.argv) != 3:
        print('用法：python upload_oss.py <本地文件> <对象名>', file=sys.stderr)
        sys.exit(1)
    sys.exit(upload(sys.argv[1], sys.argv[2]))
