#!/bin/bash
# Hermes 小票自动清理脚本
# 建议添加到 crontab: 0 2 * * * ~/.hermes/scripts/cleanup_receipts.sh

RECEIPTS_DIR="$HOME/.hermes/receipts"
RETENTION_DAYS=30

echo "🧹 清理 Hermes 小票文件 (保留最近 $RETENTION_DAYS 天)"

# 清理旧文件
find "$RECEIPTS_DIR" -name "*.json" -mtime +$RETENTION_DAYS -delete 2>/dev/null
find "$RECEIPTS_DIR" -name "*.txt" -mtime +$RETENTION_DAYS -delete 2>/dev/null

# 统计剩余文件
json_count=$(find "$RECEIPTS_DIR" -name "*.json" 2>/dev/null | wc -l)
txt_count=$(find "$RECEIPTS_DIR" -name "*.txt" 2>/dev/null | wc -l)

echo "✅ 清理完成"
echo "  剩余文件:"
echo "    JSON: $json_count 个"
echo "    TXT:  $txt_count 个"

# 如果目录太大，给出警告
dir_size=$(du -sh "$RECEIPTS_DIR" 2>/dev/null | cut -f1)
echo "  目录大小: $dir_size"

if [ "$json_count" -gt 1000 ]; then
    echo "⚠️  警告: 小票文件较多，考虑增加清理频率"
fi