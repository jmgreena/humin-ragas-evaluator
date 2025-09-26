from Text2SQLRAGSystem import Text2SQLRAGSystem
from typing import Dict, Any, List
from sqlalchemy import create_engine, text

class Text2SQLEvaluator:
    def __init__(self, rag_system: Text2SQLRAGSystem):
        self.rag_system = rag_system
        self.metrics_history = []
    
    def evaluate_single_example(self, question: str, ground_truth_sql: str, 
                              db_connection: str = None) -> Dict[str, Any]:
        """评估单个样例的多个指标:cite[9]"""
        
        # 生成SQL
        generated_sql = self.rag_system.generate_sql(question)
        
        metrics = {
            "question": question,
            "generated_sql": generated_sql,
            "ground_truth_sql": ground_truth_sql
        }
        
        # 1. 语法正确率
        syntax_score = self._evaluate_syntax(generated_sql)
        metrics["syntax_accuracy"] = syntax_score
        
        # 2. 执行准确率（如果有数据库连接）
        if db_connection and syntax_score > 0:
            exec_score = self._evaluate_execution_accuracy(generated_sql, ground_truth_sql, db_connection)
            metrics["execution_accuracy"] = exec_score
        else:
            metrics["execution_accuracy"] = 0.0
        
        # 3. 精确匹配率
        exact_match = self._evaluate_exact_match(generated_sql, ground_truth_sql)
        metrics["exact_match"] = exact_match
        
        # 4. 语义相似度
        semantic_similarity = self._evaluate_semantic_similarity(generated_sql, ground_truth_sql)
        metrics["semantic_similarity"] = semantic_similarity
        
        # 5. 检索质量评估
        retrieval_quality = self._evaluate_retrieval_quality(question, generated_sql)
        metrics["retrieval_quality"] = retrieval_quality
        
        return metrics
    
    def _evaluate_syntax(self, sql: str) -> float:
        """评估SQL语法正确性"""
        if not sql or sql.strip() == "":
            return 0.0
        
        # 简单的SQL语法检查
        basic_keywords = ["SELECT", "FROM", "WHERE", "JOIN", "GROUP BY", "ORDER BY"]
        sql_upper = sql.upper()
        
        # 检查基本结构
        has_select_from = "SELECT" in sql_upper and "FROM" in sql_upper
        if not has_select_from:
            return 0.0
        
        # 检查括号匹配
        if sql_upper.count('(') != sql_upper.count(')'):
            return 0.5
        
        # 检查基本关键字顺序
        select_pos = sql_upper.find("SELECT")
        from_pos = sql_upper.find("FROM")
        if select_pos > from_pos:
            return 0.3
        
        return 1.0
    
    def _evaluate_execution_accuracy(self, generated_sql: str, ground_truth_sql: str, 
                                   db_connection: str) -> float:
        """评估执行准确率:cite[4]"""
        try:
            engine = create_engine(db_connection)
            
            # 执行生成的SQL
            with engine.connect() as conn:
                try:
                    gen_result = conn.execute(text(generated_sql)).fetchall()
                    gen_result = [dict(row) for row in gen_result]
                except Exception as e:
                    return 0.0
            
            # 执行标准答案SQL
            with engine.connect() as conn:
                try:
                    gt_result = conn.execute(text(ground_truth_sql)).fetchall()
                    gt_result = [dict(row) for row in gt_result]
                except Exception as e:
                    return 0.0
            
            # 比较结果
            if len(gen_result) != len(gt_result):
                return 0.0
            
            # 简单比较（实际应用可能需要更复杂的比较逻辑）
            for gen_row, gt_row in zip(gen_result, gt_result):
                if gen_row != gt_row:
                    return 0.5
            
            return 1.0
            
        except Exception as e:
            print(f"执行评估错误: {e}")
            return 0.0
    
    def _evaluate_exact_match(self, generated_sql: str, ground_truth_sql: str) -> float:
        """评估精确匹配率"""
        import re
        
        # 标准化SQL进行比较
        def normalize_sql(sql):
            sql = re.sub(r'\s+', ' ', sql).upper().strip()
            sql = re.sub(r'["\'`]', '', sql)  # 移除引号
            sql = re.sub(r'/\*.*?\*/', '', sql)  # 移除注释
            return sql
        
        norm_gen = normalize_sql(generated_sql)
        norm_gt = normalize_sql(ground_truth_sql)
        
        return 1.0 if norm_gen == norm_gt else 0.0
    
    def _evaluate_semantic_similarity(self, generated_sql: str, ground_truth_sql: str) -> float:
        """评估语义相似度"""
        from sklearn.feature_extraction.text import TfidfVectorizer
        from sklearn.metrics.pairwise import cosine_similarity
        
        # 提取SQL关键元素进行比较
        def extract_sql_elements(sql):
            elements = []
            # 提取表名、列名、条件等
            import re
            tables = re.findall(r'FROM\s+(\w+)', sql.upper())
            columns = re.findall(r'SELECT\s+(.*?)\s+FROM', sql.upper())
            conditions = re.findall(r'WHERE\s+(.*?)(?:\s+GROUP BY|\s+ORDER BY|$)', sql.upper())
            
            elements.extend(tables)
            if columns:
                columns = columns[0].split(',')
                elements.extend([col.strip() for col in columns])
            if conditions:
                conditions = conditions[0].split('AND')
                elements.extend([cond.strip() for cond in conditions])
            
            return " ".join(elements)
        
        gen_elements = extract_sql_elements(generated_sql)
        gt_elements = extract_sql_elements(ground_truth_sql)
        
        if not gen_elements or not gt_elements:
            return 0.0
        
        # 计算余弦相似度
        vectorizer = TfidfVectorizer()
        try:
            tfidf_matrix = vectorizer.fit_transform([gen_elements, gt_elements])
            similarity = cosine_similarity(tfidf_matrix[0:1], tfidf_matrix[1:2])[0][0]
            return similarity
        except:
            return 0.0
    
    def _evaluate_retrieval_quality(self, question: str, generated_sql: str) -> float:
        """评估检索质量（简化版）"""
        # 这里可以扩展为更复杂的检索相关性评估
        contexts, scores = self.rag_system.retrieve_context(question)
        
        if not scores:
            return 0.0
        
        # 返回平均检索得分
        return sum(scores) / len(scores)
    
    def comprehensive_evaluation(self, test_dataset: List[Dict], db_connection: str = None) -> Dict[str, Any]:
        """全面评估在测试集上的表现"""
        
        results = []
        total_metrics = {
            "syntax_accuracy": [],
            "execution_accuracy": [],
            "exact_match": [],
            "semantic_similarity": [],
            "retrieval_quality": []
        }
        
        for i, test_case in enumerate(test_dataset):
            print(f"处理测试用例 {i+1}/{len(test_dataset)}")
            
            metrics = self.evaluate_single_example(
                test_case["question"],
                test_case["sql"],
                db_connection
            )
            
            results.append(metrics)
            
            # 汇总指标
            for key in total_metrics.keys():
                if key in metrics:
                    total_metrics[key].append(metrics[key])
        
        # 计算平均指标
        avg_metrics = {f"avg_{key}": sum(values)/len(values) if values else 0.0 
                      for key, values in total_metrics.items()}
        
        evaluation_report = {
            "total_cases": len(test_dataset),
            "results": results,
            "average_metrics": avg_metrics,
            "model_used": self.rag_system.model_name
        }
        
        self.metrics_history.append(evaluation_report)
        return evaluation_report