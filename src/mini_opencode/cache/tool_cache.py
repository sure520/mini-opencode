"""工具调用结果缓存"""
import hashlib
from typing import Optional, Dict, Any, List


class ToolCache:
    """工具调用结果缓存"""
    
    def __init__(self, max_size: int = 50):
        """初始化工具缓存
        
        Args:
            max_size: 缓存最大容量
        """
        self._cache: Dict[str, Dict[str, Any]] = {}
        self._max_size = max_size
    
    def _generate_key(self, tool_name: str, **kwargs) -> str:
        """生成缓存键
        
        Args:
            tool_name: 工具名称
            **kwargs: 工具参数
            
        Returns:
            缓存键
        """
        # 对参数进行排序以确保相同参数生成相同的键
        sorted_args = sorted(kwargs.items(), key=lambda x: x[0])
        args_str = str(sorted_args)
        key = f"{tool_name}:{args_str}"
        return hashlib.md5(key.encode()).hexdigest()
    
    def get(self, tool_name: str, **kwargs) -> Optional[Any]:
        """获取缓存的工具调用结果
        
        Args:
            tool_name: 工具名称
            **kwargs: 工具参数
            
        Returns:
            缓存的工具调用结果，未缓存返回 None
        """
        key = self._generate_key(tool_name, **kwargs)
        if key in self._cache:
            return self._cache[key]['result']
        return None
    
    def set(self, tool_name: str, result: Any, **kwargs) -> None:
        """设置工具调用结果缓存
        
        Args:
            tool_name: 工具名称
            result: 工具调用结果
            **kwargs: 工具参数
        """
        key = self._generate_key(tool_name, **kwargs)
        
        # 检查缓存大小，超出则清理
        if len(self._cache) >= self._max_size:
            # 简单的 LRU 策略：移除最早的项
            oldest_key = next(iter(self._cache))
            del self._cache[oldest_key]
        
        self._cache[key] = {
            'result': result,
            'tool_name': tool_name,
            'params': kwargs
        }
    
    def clear(self, tool_name: Optional[str] = None) -> None:
        """清理缓存
        
        Args:
            tool_name: 要清理的工具名称，None 表示清理所有缓存
        """
        if tool_name:
            # 清理指定工具的所有缓存
            keys_to_remove = []
            for key, value in self._cache.items():
                if value['tool_name'] == tool_name:
                    keys_to_remove.append(key)
            
            for key in keys_to_remove:
                del self._cache[key]
        else:
            self._cache.clear()
    
    def size(self) -> int:
        """获取缓存大小
        
        Returns:
            缓存中的项数
        """
        return len(self._cache)


# 全局工具缓存实例
tool_cache = ToolCache()
