from transformers import AutoTokenizer, AutoModelForCausalLM, pipeline
import re
from typing import Dict, List, Tuple
import torch

class LightweightText2SQLEvaluator:
    def __init__(self, model_name: str = "microsoft/phi-2", device: str = "auto"):
        """
        初始化轻量级Text2SQL评估器
        :param model_name: 轻量级LLM模型名称
        :param device: 运行设备，"auto"自动选择GPU/CPU
        """
        # 自动选择设备
        if device == "auto":
            self.device = "cuda" if torch.cuda.is_available() else "cpu"
        else:
            self.device = device
            
        # 加载模型和分词器
        self.tokenizer = AutoTokenizer.from_pretrained(model_name)
        self.model = AutoModelForCausalLM.from_pretrained(
            model_name,
            torch_dtype=torch.float16 if self.device == "cuda" else torch.float32,
            device_map=self.device
        )
        
        # 创建文本生成管道
        self.pipeline = pipeline(
            "text-generation",
            model=self.model,
            tokenizer=self.tokenizer,
            device=0 if self.device == "cuda" else -1
        )
        
        # 初始化提示词模板（针对轻量模型优化，更简洁明确）
        self.grammar_prompt = """判断以下SQL语句是否语法正确。只需回答"正确"或"错误"。
SQL: {sql}
答案:"""
        
        self.equivalence_prompt = """判断两个SQL语句在语义上是否等价，即是否会返回相同结果。
问题: {question}
SQL1: {sql1}
SQL2: {sql2}
只需回答"等价"或"不等价"。
答案:"""
        
        self.correctness_prompt = """判断SQL语句是否能正确回答问题。只需回答"正确"或"错误"。
问题: {question}
数据库结构: {schema}
SQL语句: {sql}
答案:"""

    def _clean_response(self, response: str) -> str:
        """清理模型输出，提取关键答案"""
        response = response.strip().lower()
        # 提取关键判断词
        if "正确" in response:
            return "正确"
        elif "错误" in response:
            return "错误"
        elif "等价" in response:
            return "等价"
        elif "不等价" in response:
            return "不等价"
        return ""

    def evaluate_grammar(self, sql: str) -> bool:
        """评估SQL语法正确性"""
        prompt = self.grammar_prompt.format(sql=sql)
        
        outputs = self.pipeline(
            prompt,
            max_new_tokens=5,
            temperature=0.0,
            do_sample=False,
            pad_token_id=self.tokenizer.eos_token_id
        )
        
        result = self._clean_response(outputs[0]['generated_text'][len(prompt):])
        return result == "正确"

    def evaluate_equivalence(self, question: str, sql1: str, sql2: str) -> bool:
        """评估两个SQL的语义等价性"""
        prompt = self.equivalence_prompt.format(
            question=question,
            sql1=sql1,
            sql2=sql2
        )
        
        outputs = self.pipeline(
            prompt,
            max_new_tokens=5,
            temperature=0.0,
            do_sample=False,
            pad_token_id=self.tokenizer.eos_token_id
        )
        
        result = self._clean_response(outputs[0]['generated_text'][len(prompt):])
        return result == "等价"

    def evaluate_correctness(self, question: str, sql: str, schema: str) -> bool:
        """评估SQL是否能正确回答问题"""
        prompt = self.correctness_prompt.format(
            question=question,
            schema=schema,
            sql=sql
        )
        
        outputs = self.pipeline(
            prompt,
            max_new_tokens=5,
            temperature=0.0,
            do_sample=False,
            pad_token_id=self.tokenizer.eos_token_id
        )
        
        result = self._clean_response(outputs[0]['generated_text'][len(prompt):])
        return result == "正确"

    def evaluate_single_case(
        self,
        question: str,
        generated_sql: str,
        schema: str,
        reference_sql: str = ""
    ) -> Dict:
        """评估单个Text2SQL案例"""
        # 分步评估
        grammar_ok = self.evaluate_grammar(generated_sql)
        
        if reference_sql:
            equivalent = self.evaluate_equivalence(question, generated_sql, reference_sql)
        else:
            equivalent = None  # 无参考SQL时不评估等价性
            
        correct = self.evaluate_correctness(question, generated_sql, schema)
        
        # 综合判断
        is_valid = grammar_ok and correct
        
        return {
            "grammar_correct": grammar_ok,
            "equivalent_to_reference": equivalent,
            "answers_correctly": correct,
            "is_valid": is_valid
        }

    def evaluate_batch(
        self,
        test_cases: List[Dict]
    ) -> Tuple[float, List[Dict]]:
        """批量评估测试集，返回准确率和详细结果"""
        results = []
        valid_count = 0
        
        for case in test_cases:
            eval_result = self.evaluate_single_case(
                question=case["question"],
                generated_sql=case["generated_sql"],
                schema=case["schema"],
                reference_sql=case.get("reference_sql", "")
            )
            results.append({**case,** eval_result})
            if eval_result["is_valid"]:
                valid_count += 1
        
        # 计算准确率
        accuracy = valid_count / len(test_cases) if test_cases else 0.0
        return accuracy, results


# 使用示例
if __name__ == "__main__":
    # 初始化评估器，使用轻量级模型
    # 可选模型: "microsoft/phi-2", "mistralai/Mistral-7B-Instruct-v0.2", "meta-llama/Llama-2-7b-chat-hf"等
    evaluator = LightweightText2SQLEvaluator(model_name="microsoft/phi-2")
    
    # 测试案例（Salila Text2SQL样例）
    test_cases = [
        {
            "question": "查询2023年销售额超过100万的产品名称",
            "generated_sql": "SELECT product_name FROM sales WHERE year=2023 AND revenue>1000000",
            "reference_sql": "SELECT product_name FROM sales WHERE year=2023 AND revenue>1000000",
            "schema": "表名：sales，字段：product_name（产品名称）、year（销售年份）、revenue（销售额，单位：元）"
        },
        {
            "question": "查询2023年销售额超过100万的产品名称",
            "generated_sql": "SELECT product_name FROM sales WHERE year=2023",  # 缺少条件
            "reference_sql": "SELECT product_name FROM sales WHERE year=2023 AND revenue>1000000",
            "schema": "表名：sales，字段：product_name（产品名称）、year（销售年份）、revenue（销售额，单位：元）"
        }
    ]
    
    # 批量评估
    accuracy, detailed_results = evaluator.evaluate_batch(test_cases)
    
    print(f"准确率：{accuracy:.2f}")
    for i, result in enumerate(detailed_results):
        print(f"\n案例 {i+1}:")
        print(f"生成SQL: {result['generated_sql']}")
        print(f"语法正确: {result['grammar_correct']}")
        print(f"回答正确: {result['answers_correctly']}")
        print(f"整体有效: {result['is_valid']}")
    