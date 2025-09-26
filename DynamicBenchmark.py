class DynamicBenchmark:
    """动态交互基准测试"""
    
    def create_challenge_tasks(self):
        """创建包含模糊查询、晦涩字段名等挑战性任务"""
        
        challenges = [
            {
                "type": "ambiguous_query",
                "question": "找一下那个重要的数据",  # 模糊描述
                "expected_behavior": "应该请求澄清或基于上下文合理推断"
            },
            {
                "type": "complex_join", 
                "question": "统计每个用户最近3个月的订单数量和总金额",
                "expected_behavior": "正确处理多表JOIN和时间范围"
            }
        ]
        return challenges