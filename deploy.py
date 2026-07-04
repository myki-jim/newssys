#!/usr/bin/env python3
"""
NewsSys 一键部署脚本
用法: python3 deploy.py [--frontend] [--restart]

默认只同步后端源码并重启服务。
加 --frontend 会先本地编译前端再上传。
"""
import paramiko
import os
import sys
import subprocess
import tarfile
import io
import time

HOST = "192.168.100.108"
USER = "wangshan"
PASSWORD = "jK114514."
DEPLOY_DIR = "/home/wangshan/newssys"
LOCAL_DIR = os.path.dirname(os.path.abspath(__file__))

SYNC_DIRS = ["src", "scripts"]
BACKEND_SERVICES = ["backend", "scheduler", "crawl-worker", "report-worker", "search-worker", "ai-worker"]


def ssh_connect():
    c = paramiko.SSHClient()
    c.set_missing_host_key_policy(paramiko.AutoAddPolicy())
    c.connect(HOST, username=USER, password=PASSWORD, timeout=30)
    return c


def sync_backend(client):
    """同步后端源码到服务器"""
    print("\n=== 同步后端源码 ===")

    # 打包要同步的目录
    buf = io.BytesIO()
    with tarfile.open(fileobj=buf, mode="w:gz") as tar:
        for d in SYNC_DIRS:
            path = os.path.join(LOCAL_DIR, d)
            if os.path.exists(path):
                tar.add(path, arcname=d)

    tar_bytes = buf.getvalue()
    print(f"  打包大小: {len(tar_bytes)/1024:.0f} KB")

    # 上传
    sftp = client.open_sftp()
    remote_tar = f"{DEPLOY_DIR}/sync.tar.gz"
    sftp.putfo(io.BytesIO(tar_bytes), remote_tar)
    sftp.close()

    # 解压到部署目录
    cmd = f"cd {DEPLOY_DIR} && tar xzf sync.tar.gz && rm sync.tar.gz"
    stdin, stdout, stderr = client.exec_command(cmd, timeout=30)
    err = stderr.read().decode()
    if err:
        print(f"  解压失败: {err[:200]}")
        return False
    print("  源码同步完成")
    return True


def sync_compose(client):
    """同步 docker-compose 配置文件"""
    sftp = client.open_sftp()
    local_compose = os.path.join(LOCAL_DIR, "docker-compose.prod.yml")
    sftp.put(local_compose, f"{DEPLOY_DIR}/docker-compose.prod.yml")
    # Also sync nginx config
    local_nginx = os.path.join(LOCAL_DIR, "nginx", "nginx.prod.conf")
    sftp.put(local_nginx, f"{DEPLOY_DIR}/nginx/nginx.prod.conf")
    admin_html = os.path.join(LOCAL_DIR, "nginx", "admin.html")
    sftp.put(admin_html, f"{DEPLOY_DIR}/nginx/admin.html")
    sftp.close()
    print("  docker-compose + nginx 配置同步完成")


def build_frontend():
    """本地编译前端"""
    print("\n=== 编译前端 ===")
    frontend_dir = os.path.join(LOCAL_DIR, "frontend")
    result = subprocess.run(
        ["npm", "run", "build:only"],
        cwd=frontend_dir,
        capture_output=True, text=True,
        timeout=120,
    )
    if result.returncode != 0:
        print("  编译失败!")
        print(result.stderr[-500:])
        return None
    print("  编译完成")
    return os.path.join(frontend_dir, "dist")


def sync_frontend(client):
    """上传前端编译产物"""
    dist = build_frontend()
    if dist is None:
        return False

    print("\n=== 上传前端 ===")
    buf = io.BytesIO()
    with tarfile.open(fileobj=buf, mode="w:gz") as tar:
        tar.add(dist, arcname="dist")
    tar_bytes = buf.getvalue()

    sftp = client.open_sftp()
    sftp.putfo(io.BytesIO(tar_bytes), f"{DEPLOY_DIR}/frontend-dist.tar.gz")
    sftp.close()

    cmd = f"""
    cd {DEPLOY_DIR}
    tar xzf frontend-dist.tar.gz
    rm frontend-dist.tar.gz
    for c in $(sg docker -c 'docker ps --filter name=frontend -q'); do
        sg docker -c "docker cp dist/. $c:/usr/share/nginx/html/"
    done
    rm -rf dist
    """
    stdin, stdout, stderr = client.exec_command(cmd, timeout=30)
    err = stderr.read().decode()
    if err:
        print(f"  上传失败: {err[:200]}")
        return False
    print("  前端更新完成")
    return True


def restart_services(client, frontend_too=False):
    """重启服务使代码生效"""
    print("\n=== 重启服务 ===")
    services = " ".join(BACKEND_SERVICES)
    if frontend_too:
        services += " frontend"

    cmd = f"cd {DEPLOY_DIR} && sg docker -c 'docker compose -f docker-compose.prod.yml up -d --force-recreate {services} 2>&1'"
    stdin, stdout, stderr = client.exec_command(cmd, timeout=120)
    out = stdout.read().decode()
    err = stderr.read().decode()
    # 只显示最后几行
    lines = out.strip().split("\n")
    for line in lines[-10:]:
        if line.strip():
            print(f"  {line.strip()}")
    if err:
        print(f"  ERR: {err[-300:]}")

    # 等待服务稳定
    print("  等待服务启动...")
    time.sleep(8)

    # 检查状态
    stdin, stdout, stderr = client.exec_command(
        "sg docker -c 'docker ps --format \"table {{.Names}}\\t{{.Status}}\"'",
        timeout=10,
    )
    print(stdout.read().decode())


def main():
    args = sys.argv[1:]
    do_frontend = "--frontend" in args

    print("=" * 50)
    print("NewsSys 部署")
    print("=" * 50)

    try:
        client = ssh_connect()
        print("已连接到服务器")
    except Exception as e:
        print(f"连接失败: {e}")
        return 1

    try:
        # 1. 同步 compose 配置（含新的 volume 挂载）
        sync_compose(client)

        # 2. 同步后端源码
        if not sync_backend(client):
            return 1

        # 3. 前端（可选）
        if do_frontend:
            if not sync_frontend(client):
                return 1

        # 4. 重启服务
        restart_services(client, frontend_too=do_frontend)

        print("\n" + "=" * 50)
        print("部署完成!")
        print(f"访问: http://{HOST}")
        print("=" * 50)

    finally:
        client.close()


if __name__ == "__main__":
    raise SystemExit(main())
