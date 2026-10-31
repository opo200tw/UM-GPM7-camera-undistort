#!/bin/bash

RTSP_URL="rtsp://192.168.0.31:8080"
OUTPUT_FILE="thermal_video.mkv"
DEBUG_LEVEL="3"

if [ $# -eq 1 ]; then
    RTSP_URL=$1
fi

if [ $# -eq 2 ]; then
    RTSP_URL=$1
    OUTPUT_FILE=$2
fi

if [[ ! "$RTSP_URL" =~ ^rtsp:// ]]; then
    RTSP_URL="rtsp://$RTSP_URL"
fi

if [[ ! "$RTSP_URL" =~ :[0-9]+ ]]; then
    RTSP_URL="$RTSP_URL:8080"
fi

echo "開始錄製 RTSP 串流..."
echo "URL: $RTSP_URL"
echo "輸出文件: $OUTPUT_FILE"
echo "按 Ctrl+C 停止錄製"

export GST_DEBUG=$DEBUG_LEVEL

# -e: Ctrl-C sends EOS first, so matroskamux finishes the file
gst-launch-1.0 -e --gst-debug-level=$DEBUG_LEVEL \
    rtspsrc location="$RTSP_URL" latency=0 buffer-mode=auto ! \
    rtph264depay ! h264parse ! tee name=t \
    t. ! queue ! matroskamux ! filesink location="$OUTPUT_FILE" \
    t. ! queue ! avdec_h264 ! videoconvert ! autovideosink sync=false

if [ $? -eq 0 ]; then
    echo "錄製完成: $OUTPUT_FILE"
else
    echo "錄製失敗，請檢查指令與參數"
    echo "請確認 RTSP URL 是否正確: $RTSP_URL"
    echo "嘗試使用備用 pipeline..."
    
    gst-launch-1.0 -e --gst-debug-level=$DEBUG_LEVEL \
        rtspsrc location="$RTSP_URL" latency=0 ! \
        decodebin ! videoconvert ! x264enc ! matroskamux ! \
        filesink location="$OUTPUT_FILE"
    
    if [ $? -eq 0 ]; then
        echo "備用 pipeline 錄製完成: $OUTPUT_FILE"
    else
        echo "所有 pipeline 都失敗，請檢查網路連接和 RTSP URL"
        exit 1
    fi
fi 