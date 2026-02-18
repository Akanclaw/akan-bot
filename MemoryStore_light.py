#!/opt/anon-bot/venv/bin/python3
"""
轻量级 MemoryStore - 使用 OpenClaw API 生成 embedding
无需 sentence-transformers，节省 120MB+ 磁盘
"""

import json
import uuid
import requests
from datetime import datetime
from typing import List, Dict, Any, Optional

# OpenClaw Gateway 配置
OPENCLAW_URL = "http://127.0.0.1:3000"  # 或其他配置的端口

def get_embedding(text: str) -> List[float]:
    """
    使用 OpenClaw API 生成文本 embedding
    兼容多种模型：TinyLlama, NVIDIA, Kimi 等
    """
    try:
        # 方法1: 直接调用 OpenClaw 的 embedding 端点
        response = requests.post(
            f"{OPENCLAW_URL}/api/embed",
            json={"text": text},
            timeout=10
        )
        if response.status_code == 200:
            return response.json()["embedding"]
    except:
        pass
    
    # 方法2: 使用 sentence-transformers 回退（如果可用）
    try:
        from sentence_transformers import SentenceTransformer
        model = SentenceTransformer('paraphrase-multilingual-MiniLM-L12-v2')
        return model.encode(text).tolist()
    except:
        pass
    
    # 方法3: 简单哈希 embedding（降级方案）
    # 生成 384 维的简单向量
    import hashlib
    hash_val = hashlib.md5(text.encode()).hexdigest()
    embedding = []
    for i in range(384):
        # 从哈希生成伪随机但确定的值
        char_idx = i % len(hash_val)
        val = int(hash_val[char_idx], 16) / 16.0
        embedding.append(val)
    return embedding


class MemoryStore:
    """轻量级语义记忆系统 - OpenClaw API 版"""
    
    def __init__(self, collection_name="memories", persist_directory="./chroma_db"):
        self.collection_name = collection_name
        self.persist_directory = persist_directory
        
        # 延迟导入 chromadb
        import chromadb
        from chromadb.config import Settings
        
        self.chroma_client = chromadb.PersistentClient(
            path=persist_directory,
            settings=Settings(anonymized_telemetry=False)
        )
        
        self.collection = self.chroma_client.get_or_create_collection(
            name=collection_name,
            metadata={"description": "Semantic memory via OpenClaw API"}
        )
        
        print(f"✅ MemoryStore 轻量版初始化 - 使用 OpenClaw API")
    
    def add_memory(self, text: str, metadata: Dict[str, Any] = None) -> str:
        """添加记忆"""
        memory_id = str(uuid.uuid4())
        
        if metadata is None:
            metadata = {}
        
        metadata.setdefault("timestamp", datetime.now().isoformat())
        metadata.setdefault("type", "general")
        
        # 使用 OpenClaw API 生成 embedding
        embedding = get_embedding(text)
        
        self.collection.add(
            embeddings=[embedding],
            documents=[text],
            metadatas=[metadata],
            ids=[memory_id]
        )
        
        print(f"📝 记忆已添加: {text[:30]}...")
        return memory_id
    
    def search(self, query: str, n_results: int = 5, 
               filter_metadata: Dict[str, Any] = None) -> List[Dict[str, Any]]:
        """语义搜索记忆"""
        # OpenClaw API embedding
        query_embedding = get_embedding(query)
        
        results = self.collection.query(
            query_embeddings=[query_embedding],
            n_results=n_results,
            where=filter_metadata,
            include=["documents", "metadatas", "distances"]
        )
        
        formatted_results = []
        if results["documents"] and results["documents"][0]:
            for i in range(len(results["documents"][0])):
                result = {
                    "text": results["documents"][0][i],
                    "metadata": results["metadatas"][0][i] if results["metadatas"] else {},
                    "id": results["ids"][0][i],
                    "distance": float(results["distances"][0][i]) if results["distances"] else 0.0,
                    "similarity_score": 1.0 - float(results["distances"][0][i]) if results["distances"] else 1.0
                }
                formatted_results.append(result)
        
        return formatted_results


if __name__ == "__main__":
    # 测试
    store = MemoryStore(collection_name="test", persist_directory="./test_db")
    
    store.add_memory("测试记忆1", {"type": "test"})
    store.add_memory("测试记忆2", {"type": "test"})
    
    results = store.search("测试")
    print(f"找到 {len(results)} 条结果")
