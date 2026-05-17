'''
node节点中的数据库交互
'''
import mysql.connector
import logging
from app.db import get_read_connection
# 这些函数帮助节点与应用程序的数据库进行交互，以获取文件等资源。
def get_file_content(user_id: int, filename: str) -> bytes | None:
    """从数据库为指定用户获取文件内容。"""
    try:
        with get_read_connection(consistency="strong") as conn:
            cursor = conn.cursor(dictionary=True)
            cursor.execute(
                "SELECT file_content FROM uploaded_files WHERE user_id = %s AND original_filename = %s ORDER BY last_accessed_at DESC LIMIT 1",
                (user_id, filename)
            )
            result = cursor.fetchone()
            return result['file_content'] if result else None
    except mysql.connector.Error as e:
        logging.error(f"Agent Node: 从数据库获取文件 '{filename}' (用户ID: {user_id}) 时出错: {e}")
        return None

def get_recent_file(user_id: int) -> tuple[bytes | None, str | None]:
    """获取用户最近上传或访问的文件的内容和名称。"""
    try:
        with get_read_connection(consistency="strong") as conn:
            cursor = conn.cursor(dictionary=True)
            cursor.execute(
                "SELECT file_content, original_filename FROM uploaded_files WHERE user_id = %s ORDER BY last_accessed_at DESC LIMIT 1",
                (user_id,)
            )
            result = cursor.fetchone()
            if result:
                return result['file_content'], result['original_filename']
            return None, None
    except mysql.connector.Error as e:
        logging.error(f"Agent Node: 为用户 {user_id} 获取最近文件时出错: {e}")
        return None, None
