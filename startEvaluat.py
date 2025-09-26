from Text2SQLRAGSystem import Text2SQLRAGSystem
from Text2SQLEvaluator import Text2SQLEvaluator
import json
from RAGASAssessment import RAGASAssessment

def main():
    """完整的评估流程示例"""
    
    # 1. 初始化RAG系统
    rag_system = Text2SQLRAGSystem(
        model_name="qwen2.5:3b",
        db_connection="mysql+pymysql://root:Rzx_1218@localhost/test_db"
    )
    
    # 2. 训练RAG模型（一次性操作）
    rag_system.train_rag_model(
        ddl_files=["data/ddl.sql"],
        doc_files=["data/documentations.txt"], 
        example_files=["data/question-sql.txt"]
    )
    
    # 3. 准备测试数据
    test_cases = [
        {
            "question": "查询复购用户",
            "sql": "SELECT user_id, COUNT(*) AS order_count FROM orders GROUP BY"
        },
        {
            "question": "显示最近一周的库存变动", 
            "sql": "SELECT * FROM inventory_logs WHERE created_at >= DATE_SUB(CURDATE(), INTERVAL 7 DAY) ORDER BY created_at DESC"
        }
    ]
    
    # 4. 执行评估
    evaluator = Text2SQLEvaluator(rag_system)
    comprehensive_report = evaluator.comprehensive_evaluation(test_cases)

    # 5. RAGAS增强评估
    ragas_assessor = RAGASAssessment(rag_system)
    ragas_scores = ragas_assessor.evaluate_with_ragas(test_cases)
    
    # 6. 生成最终报告
    final_report = {
        "comprehensive_evaluation": comprehensive_report,
        "ragas_assessment": ragas_scores,
        "timestamp": "2025-09-26"
    }
    
    # 保存报告
    with open("evaluation_report.json", "w", encoding="utf-8") as f:
        json.dump(final_report, f, ensure_ascii=False, indent=2)
    
    print("评估完成！报告已保存至 evaluation_report.json")
    
    # 打印关键指标
    avg_metrics = comprehensive_report["average_metrics"]
    print("\n=== 关键评估指标 ===")
    for metric, value in avg_metrics.items():
        print(f"{metric}: {value:.3f}")
    
    for metric, value in ragas_scores.items():
        print(f"{metric}: {value:.3f}")

if __name__ == "__main__":
    main()