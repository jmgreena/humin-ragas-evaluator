import chromadb
from chromadb.config import Settings
import sqlalchemy as db
from sqlalchemy import create_engine, text
from typing import List, Dict, Any, Tuple
import json
import numpy as np

class Text2SQLRAGSystem:
    def __init__(self, model_name: str = "qwen2.5-code:7b", db_connection: str = None):
        self.model_name = model_name
        #self.chroma_client = chromadb.Client(Settings(
        #    chroma_db_impl="duckdb+parquet",
        #    persist_directory="./chroma_db"
        #))
        self.chroma_client = chromadb.PersistentClient(path="./chroma_db")
        
        # 初始化向量集合
        self.collection = self.chroma_client.get_or_create_collection(name="text2sql_knowledge")
        
        # 数据库连接
        if db_connection:
            self.engine = create_engine(db_connection)
        else:
            self.engine = None
            
        # 初始化嵌入函数（使用本地模型）
        self.embedding_function = self._get_embedding_function()
    
    def _get_embedding_function(self):
        """使用本地嵌入模型"""
        try:
            from langchain.embeddings import HuggingFaceEmbeddings
            embeddings = HuggingFaceEmbeddings(
                model_name="BAAI/bge-small-zh-v1.5",
                model_kwargs={'device': 'cpu'}
            )
            return embeddings
        except:
            # 回退到简单嵌入
            return self._simple_embedding
    
    def _simple_embedding(self, texts: List[str]) -> List[List[float]]:
        """简单的词频嵌入作为备选"""
        from collections import defaultdict
        import math
        
        embeddings = []
        for text in texts:
            words = text.lower().split()
            word_count = defaultdict(int)
            for word in words:
                word_count[word] += 1
            
            # 简单的归一化向量
            if word_count:
                vector = list(word_count.values())
                norm = math.sqrt(sum(x*x for x in vector))
                normalized_vector = [x/norm for x in vector]
                # 填充或截断为固定维度
                if len(normalized_vector) < 512:
                    normalized_vector.extend([0] * (512 - len(normalized_vector)))
                else:
                    normalized_vector = normalized_vector[:512]
                embeddings.append(normalized_vector)
            else:
                embeddings.append([0] * 512)
        
        return embeddings
    
    def train_rag_model(self, ddl_files: List[str], doc_files: List[str], example_files: List[str]):
        """训练RAG模型：导入DDL、文档和示例:cite[4]"""
        
        all_documents = []
        metadatas = []
        ids = []
        
        # 处理DDL文件
        for ddl_file in ddl_files:
            with open(ddl_file, 'r', encoding='utf-8') as f:
                for i, line in enumerate(f):
                    if line.strip():
                        all_documents.append(line.strip())
                        metadatas.append({"type": "ddl", "source": ddl_file})
                        ids.append(f"ddl_{ddl_file}_{i}")
        
        # 处理文档文件
        for doc_file in doc_files:
            with open(doc_file, 'r', encoding='utf-8') as f:
                for i, line in enumerate(f):
                    if line.strip():
                        all_documents.append(line.strip())
                        metadatas.append({"type": "documentation", "source": doc_file})
                        ids.append(f"doc_{doc_file}_{i}")
        
        # 处理示例文件
        for example_file in example_files:
            with open(example_file, 'r', encoding='utf-8') as f:
                for i, line in enumerate(f):
                    if line.strip():
                        all_documents.append(line.strip())
                        metadatas.append({"type": "example", "source": example_file})
                        ids.append(f"ex_{example_file}_{i}")
        
        # 批量添加到向量数据库
        batch_size = 100
        for i in range(0, len(all_documents), batch_size):
            batch_docs = all_documents[i:i+batch_size]
            batch_metas = metadatas[i:i+batch_size]
            batch_ids = ids[i:i+batch_size]
            
            # 生成嵌入
            embeddings = self.embedding_function.embed_documents(batch_docs)
            
            self.collection.add(
                embeddings=embeddings,
                documents=batch_docs,
                metadatas=batch_metas,
                ids=batch_ids
            )
        
        print(f"成功导入 {len(all_documents)} 条知识条目")
    
    def retrieve_context(self, question: str, n_results: int = 5) -> Tuple[List[str], List[float]]:
        """检索与问题相关的上下文:cite[2]"""
        
        # 生成问题嵌入
        question_embedding = self.embedding_function.embed_query(question)
        
        # 检索相似内容
        results = self.collection.query(
            query_embeddings=[question_embedding],
            n_results=n_results,
            include=["documents", "distances", "metadatas"]
        )
        
        contexts = results['documents'][0] if results['documents'] else []
        scores = [1 - (distance / 10) for distance in results['distances'][0]] if results['distances'] else []
        
        return contexts, scores
    
    def generate_sql(self, question: str, contexts: List[str] = None) -> str:
        """使用Ollama本地模型生成SQL:cite[3]"""
        
        import ollama
        
        if contexts is None:
            contexts, _ = self.retrieve_context(question)
        
        # 构建prompt:cite[5]:cite[9]
        prompt = self._build_prompt(question, contexts)
        
        try:
            response = ollama.generate(
                model=self.model_name,
                prompt=prompt,
                options={
                    'temperature': 0.1,
                    'top_p': 0.9,
                    'num_predict': 500
                }
            )
            
            sql = response['response'].strip()
            # 清理SQL输出
            sql = self._clean_sql_output(sql)
            return sql
            
        except Exception as e:
            print(f"SQL生成错误: {e}")
            return ""
    
    def _build_prompt(self, question: str, contexts: List[str]) -> str:
        """构建优化的prompt模板:cite[5]"""
        
        context_str = "\n".join([f"- {ctx}" for ctx in contexts])
        
        prompt = f"""你是一名专业的SQL专家。请根据以下数据库上下文信息，将自然语言问题转换为准确且可执行的SQL查询。

数据库上下文信息：
{context_str}

自然语言问题：{question}

请遵循以下要求：
1. 只返回SQL查询语句，不要任何解释
2. 确保SQL语法正确且符合数据库规范
3. 使用合适的JOIN条件和WHERE子句
4. 如果问题涉及聚合，使用正确的聚合函数
5. 如果上下文信息不足，基于常见SQL模式进行合理推断

SQL查询："""
        
        return prompt
    
    def _clean_sql_output(self, sql: str) -> str:
        """清理SQL输出，移除markdown代码块等"""
        import re
        
        # 移除```sql ... ```包装
        sql = re.sub(r'```sql\s*', '', sql)
        sql = re.sub(r'\s*```', '', sql)
        
        # 移除多余的空白字符
        sql = re.sub(r'\s+', ' ', sql).strip()
        
        return sql