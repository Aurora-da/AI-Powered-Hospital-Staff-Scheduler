import os
import pandas as pd
from config import DATA_DIR, EXCEL_ENGINE, logger

def export_schedule(df: pd.DataFrame, filename: str = "schedule_result.xlsx"):
    """导出排班结果"""
    full_path = os.path.join(DATA_DIR, filename)
    df.to_excel(full_path, index=False, engine=EXCEL_ENGINE)
    logger.info(f"排班结果已导出到: {full_path}")

def export_history(df: pd.DataFrame, filename: str = "schedule_history.xlsx"):
    """导出排班历史（追加模式）"""
    full_path = os.path.join(DATA_DIR, filename)
    
    # 如果文件不存在，创建新文件；否则追加
    if os.path.exists(full_path):
        history_df = pd.read_excel(full_path, engine=EXCEL_ENGINE)
        new_df = pd.concat([history_df, df], ignore_index=True)
    else:
        new_df = df
    
    new_df.to_excel(full_path, index=False, engine=EXCEL_ENGINE)
    logger.info(f"排班历史已更新到: {full_path}")

def export_swap_result(df: pd.DataFrame, filename: str = "swap_history.xlsx"):
    """导出调班结果"""
    full_path = os.path.join(DATA_DIR, filename)
    
    if os.path.exists(full_path):
        swap_history = pd.read_excel(full_path, engine=EXCEL_ENGINE)
        new_df = pd.concat([swap_history, df], ignore_index=True)
    else:
        new_df = df
    
    new_df.to_excel(full_path, index=False, engine=EXCEL_ENGINE)
    logger.info(f"调班结果已导出到: {full_path}")