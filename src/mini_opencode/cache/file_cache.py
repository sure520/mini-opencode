"""基于文件哈希的缓存"""
import os
import hashlib
from typing import Optional, Dict, Any


class FileCache:
    """文件内容缓存"""
    
    def __init__(self, max_size: int = 100):
        """初始化文件缓存
        
        Args:
            max_size: 缓存最大容量
        """
        self._cache: Dict[str, Dict[str, Any]] = {}
        self._max_size = max_size
    
    def _get_file_hash(self, file_path: str) -> Optional[str]:
        """获取文件哈希值
        
        Args:
            file_path: 文件路径
            
        Returns:
            文件哈希值，文件不存在返回 None
        """
        if not os.path.exists(file_path):
            return None
        
        try:
            with open(file_path, 'rb') as f:
                content = f.read()
                return hashlib.md5(content).hexdigest()
        except Exception:
            return None
    
    def get(self, file_path: str) -> Optional[str]:
        """获取缓存的文件内容
        
        Args:
            file_path: 文件路径
            
        Returns:
            缓存的文件内容，未缓存或文件已变化返回 None
        """
        file_hash = self._get_file_hash(file_path)
        if not file_hash:
            return None
        
        if file_path in self._cache:
            cached_data = self._cache[file_path]
            if cached_data['hash'] == file_hash:
                return cached_data['content']
        
        return None
    
    def set(self, file_path: str, content: str) -> None:
        """设置文件缓存
        
        Args:
            file_path: 文件路径
            content: 文件内容
        """
        # 直接根据传入的内容计算哈希值，而不是依赖文件系统
        file_hash = hashlib.md5(content.encode()).hexdigest()
        
        # 检查缓存大小，超出则清理
        if len(self._cache) >= self._max_size:
            # 简单的 LRU 策略：移除最早的项
            oldest_key = next(iter(self._cache))
            del self._cache[oldest_key]
        
        self._cache[file_path] = {
            'hash': file_hash,
            'content': content
        }
    
    def clear(self, file_path: Optional[str] = None) -> None:
        """清理缓存
        
        Args:
            file_path: 要清理的文件路径，None 表示清理所有缓存
        """
        if file_path:
            if file_path in self._cache:
                del self._cache[file_path]
        else:
            self._cache.clear()
    
    def size(self) -> int:
        """获取缓存大小
        
        Returns:
            缓存中的文件数量
        """
        return len(self._cache)


# 全局文件缓存实例
file_cache = FileCache()
