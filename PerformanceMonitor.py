class PerformanceMonitor:
    """资源使用监控"""
    
    def monitor_inference(self):
        """监控推理时间和内存使用"""
        import psutil
        import time
        
        start_time = time.time()
        start_memory = psutil.Process().memory_info().rss / 1024 / 1024  # MB
        
        # 执行推理...
        
        end_time = time.time()
        end_memory = psutil.Process().memory_info().rss / 1024 / 1024
        
        return {
            "inference_time": end_time - start_time,
            "memory_usage": end_memory - start_memory
        }