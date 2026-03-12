-- Savant 视频分析系统 - 数据库初始化脚本（优化版）

-- 1. 视频源表
CREATE TABLE IF NOT EXISTS sources (
    id SERIAL PRIMARY KEY,
    source_id VARCHAR(50) UNIQUE NOT NULL,
    name VARCHAR(100),
    location VARCHAR(255),
    type VARCHAR(20) CHECK (type IN ('file', 'rtsp', 'usb', 'http')),
    enabled BOOLEAN DEFAULT true,
    created_at TIMESTAMP DEFAULT NOW(),
    updated_at TIMESTAMP DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_sources_source_id ON sources(source_id);
CREATE INDEX IF NOT EXISTS idx_sources_enabled ON sources(enabled);

COMMENT ON TABLE sources IS '视频源信息表';
COMMENT ON COLUMN sources.source_id IS '视频源唯一标识';
COMMENT ON COLUMN sources.type IS '视频源类型: file, rtsp, usb, http';

-- 2. AI 模型表
CREATE TABLE IF NOT EXISTS models (
    id SERIAL PRIMARY KEY,
    model_name VARCHAR(50) UNIQUE NOT NULL,
    model_type VARCHAR(50),
    version VARCHAR(20),
    description TEXT,
    created_at TIMESTAMP DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_models_model_name ON models(model_name);

COMMENT ON TABLE models IS 'AI 模型信息表';
COMMENT ON COLUMN models.model_type IS '模型类型: detector, classifier, tracker';

-- 3. 帧级别检测结果表
CREATE TABLE IF NOT EXISTS frame_detections (
    id BIGSERIAL PRIMARY KEY,
    source_id INTEGER NOT NULL REFERENCES sources(id),
    model_id INTEGER NOT NULL REFERENCES models(id),
    frame_num INTEGER NOT NULL,
    timestamp TIMESTAMP NOT NULL,
    fps FLOAT,
    object_count INTEGER DEFAULT 0,
    processing_time_ms FLOAT,
    created_at TIMESTAMP DEFAULT NOW(),
    UNIQUE(source_id, model_id, frame_num, timestamp)
);

-- 索引
CREATE INDEX IF NOT EXISTS idx_frame_detections_source ON frame_detections(source_id);
CREATE INDEX IF NOT EXISTS idx_frame_detections_model ON frame_detections(model_id);
CREATE INDEX IF NOT EXISTS idx_frame_detections_timestamp ON frame_detections(timestamp DESC);
CREATE INDEX IF NOT EXISTS idx_frame_detections_source_time ON frame_detections(source_id, timestamp DESC);

COMMENT ON TABLE frame_detections IS '帧级别检测结果表';
COMMENT ON COLUMN frame_detections.object_count IS '检测到的对象数量（冗余字段，用于快速统计）';
COMMENT ON COLUMN frame_detections.processing_time_ms IS '处理耗时（毫秒）';

-- 4. 对象级别检测结果表
CREATE TABLE IF NOT EXISTS detected_objects (
    id BIGSERIAL PRIMARY KEY,
    frame_detection_id BIGINT NOT NULL REFERENCES frame_detections(id) ON DELETE CASCADE,
    object_class VARCHAR(50) NOT NULL,
    confidence FLOAT NOT NULL CHECK (confidence >= 0 AND confidence <= 1),
    bbox_x INTEGER NOT NULL,
    bbox_y INTEGER NOT NULL,
    bbox_width INTEGER NOT NULL CHECK (bbox_width > 0),
    bbox_height INTEGER NOT NULL CHECK (bbox_height > 0),
    track_id INTEGER,
    attributes JSONB,
    created_at TIMESTAMP DEFAULT NOW()
);

-- 索引
CREATE INDEX IF NOT EXISTS idx_detected_objects_frame ON detected_objects(frame_detection_id);
CREATE INDEX IF NOT EXISTS idx_detected_objects_class ON detected_objects(object_class);
CREATE INDEX IF NOT EXISTS idx_detected_objects_confidence ON detected_objects(confidence);
CREATE INDEX IF NOT EXISTS idx_detected_objects_track ON detected_objects(track_id) WHERE track_id IS NOT NULL;
CREATE INDEX IF NOT EXISTS idx_detected_objects_class_confidence ON detected_objects(object_class, confidence);

COMMENT ON TABLE detected_objects IS '对象级别检测结果表';
COMMENT ON COLUMN detected_objects.frame_detection_id IS '关联的帧检测记录';
COMMENT ON COLUMN detected_objects.object_class IS '对象类别（person, car, etc.）';
COMMENT ON COLUMN detected_objects.confidence IS '置信度（0-1）';
COMMENT ON COLUMN detected_objects.track_id IS '可选，用于对象追踪';
COMMENT ON COLUMN detected_objects.attributes IS '可选，额外属性（JSONB 格式）';

-- 5. 小时级统计表
CREATE TABLE IF NOT EXISTS hourly_statistics (
    id SERIAL PRIMARY KEY,
    source_id INTEGER NOT NULL REFERENCES sources(id),
    model_id INTEGER NOT NULL REFERENCES models(id),
    stat_hour TIMESTAMP NOT NULL,
    total_frames INTEGER DEFAULT 0,
    total_objects INTEGER DEFAULT 0,
    object_class_counts JSONB,
    avg_confidence FLOAT,
    avg_processing_time_ms FLOAT,
    created_at TIMESTAMP DEFAULT NOW(),
    updated_at TIMESTAMP DEFAULT NOW(),
    UNIQUE(source_id, model_id, stat_hour)
);

CREATE INDEX IF NOT EXISTS idx_hourly_stats_hour ON hourly_statistics(stat_hour DESC);
CREATE INDEX IF NOT EXISTS idx_hourly_stats_source_model ON hourly_statistics(source_id, model_id);

COMMENT ON TABLE hourly_statistics IS '小时级统计信息表';
COMMENT ON COLUMN hourly_statistics.stat_hour IS '统计时间（精确到小时）';
COMMENT ON COLUMN hourly_statistics.object_class_counts IS '对象类别计数（JSONB 格式）: {"person": 100, "car": 50}';

-- 6. 创建视图：最近 24 小时统计
CREATE OR REPLACE VIEW recent_statistics AS
SELECT
    s.source_id,
    m.model_name,
    hs.stat_hour,
    hs.total_frames,
    hs.total_objects,
    hs.object_class_counts,
    hs.avg_confidence,
    hs.avg_processing_time_ms
FROM hourly_statistics hs
JOIN sources s ON hs.source_id = s.id
JOIN models m ON hs.model_id = m.id
WHERE hs.stat_hour >= NOW() - INTERVAL '24 hours'
ORDER BY hs.stat_hour DESC;

COMMENT ON VIEW recent_statistics IS '最近 24 小时统计数据';

-- 7. 创建函数：更新统计信息
CREATE OR REPLACE FUNCTION update_statistics()
RETURNS TRIGGER AS $$
DECLARE
    stat_hour_val TIMESTAMP;
BEGIN
    -- 计算小时时间戳
    stat_hour_val := DATE_TRUNC('hour', NEW.timestamp);

    -- 更新或插入统计记录
    INSERT INTO hourly_statistics (
        source_id,
        model_id,
        stat_hour,
        total_frames,
        total_objects,
        avg_processing_time_ms,
        updated_at
    )
    VALUES (
        NEW.source_id,
        NEW.model_id,
        stat_hour_val,
        1,
        NEW.object_count,
        NEW.processing_time_ms,
        NOW()
    )
    ON CONFLICT (source_id, model_id, stat_hour)
    DO UPDATE SET
        total_frames = hourly_statistics.total_frames + 1,
        total_objects = hourly_statistics.total_objects + NEW.object_count,
        avg_processing_time_ms = (
            COALESCE(hourly_statistics.avg_processing_time_ms, 0) * hourly_statistics.total_frames +
            COALESCE(NEW.processing_time_ms, 0)
        ) / (hourly_statistics.total_frames + 1),
        updated_at = NOW();

    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

COMMENT ON FUNCTION update_statistics() IS '自动更新统计信息的触发器函数';

-- 8. 创建触发器
DROP TRIGGER IF EXISTS trigger_update_statistics ON frame_detections;
CREATE TRIGGER trigger_update_statistics
    AFTER INSERT ON frame_detections
    FOR EACH ROW
    EXECUTE FUNCTION update_statistics();

-- 9. 创建函数：更新对象类别统计
CREATE OR REPLACE FUNCTION update_object_class_counts()
RETURNS TRIGGER AS $$
DECLARE
    stat_hour_val TIMESTAMP;
    current_counts JSONB;
    new_count INTEGER;
BEGIN
    -- 计算小时时间戳
    SELECT DATE_TRUNC('hour', fd.timestamp) INTO stat_hour_val
    FROM frame_detections fd
    WHERE fd.id = NEW.frame_detection_id;

    -- 获取当前统计
    SELECT hs.object_class_counts INTO current_counts
    FROM hourly_statistics hs
    JOIN frame_detections fd ON fd.source_id = hs.source_id AND fd.model_id = hs.model_id
    WHERE fd.id = NEW.frame_detection_id
    AND hs.stat_hour = stat_hour_val;

    -- 如果没有统计记录，初始化为空对象
    IF current_counts IS NULL THEN
        current_counts := '{}'::JSONB;
    END IF;

    -- 更新对象类别计数
    new_count := COALESCE((current_counts->>NEW.object_class)::INTEGER, 0) + 1;
    current_counts := jsonb_set(current_counts, ARRAY[NEW.object_class], to_jsonb(new_count));

    -- 更新统计表
    UPDATE hourly_statistics hs
    SET object_class_counts = current_counts,
        updated_at = NOW()
    FROM frame_detections fd
    WHERE fd.id = NEW.frame_detection_id
    AND hs.source_id = fd.source_id
    AND hs.model_id = fd.model_id
    AND hs.stat_hour = stat_hour_val;

    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

COMMENT ON FUNCTION update_object_class_counts() IS '自动更新对象类别统计的触发器函数';

-- 10. 创建触发器
DROP TRIGGER IF EXISTS trigger_update_object_class_counts ON detected_objects;
CREATE TRIGGER trigger_update_object_class_counts
    AFTER INSERT ON detected_objects
    FOR EACH ROW
    EXECUTE FUNCTION update_object_class_counts();

-- 11. 创建函数：清理旧数据
CREATE OR REPLACE FUNCTION cleanup_old_data(retention_days INTEGER DEFAULT 30)
RETURNS TABLE(deleted_frames BIGINT, deleted_objects BIGINT) AS $$
DECLARE
    frame_count BIGINT;
    object_count BIGINT;
BEGIN
    -- 删除超过保留期的帧检测记录（级联删除对象）
    DELETE FROM frame_detections
    WHERE timestamp < NOW() - (retention_days || ' days')::INTERVAL;

    GET DIAGNOSTICS frame_count = ROW_COUNT;

    -- 删除超过保留期的统计记录
    DELETE FROM hourly_statistics
    WHERE stat_hour < NOW() - (retention_days || ' days')::INTERVAL;

    RAISE NOTICE '清理了 % 条帧记录（保留 % 天）', frame_count, retention_days;

    RETURN QUERY SELECT frame_count, 0::BIGINT;
END;
$$ LANGUAGE plpgsql;

COMMENT ON FUNCTION cleanup_old_data(INTEGER) IS '清理超过保留期的检测结果';

-- 12. 插入初始数据
INSERT INTO sources (source_id, name, location, type) VALUES
    ('video1', '视频源 1', '/videos/video1.mp4', 'file'),
    ('video2', '视频源 2', '/videos/video2.mp4', 'file'),
    ('video3', '视频源 3', '/videos/video3.mp4', 'file')
ON CONFLICT (source_id) DO NOTHING;

INSERT INTO models (model_name, model_type, version, description) VALUES
    ('yolov8', 'detector', 'v8n', 'YOLOv8 目标检测模型'),
    ('peoplenet', 'detector', 'resnet34', 'PeopleNet 人员检测模型')
ON CONFLICT (model_name) DO NOTHING;

-- 13. 授权
GRANT ALL PRIVILEGES ON ALL TABLES IN SCHEMA public TO savant;
GRANT ALL PRIVILEGES ON ALL SEQUENCES IN SCHEMA public TO savant;
GRANT EXECUTE ON ALL FUNCTIONS IN SCHEMA public TO savant;

-- 14. 创建常用查询的物化视图（可选，用于性能优化）
CREATE MATERIALIZED VIEW IF NOT EXISTS daily_object_counts AS
SELECT
    s.source_id,
    m.model_name,
    DATE(fd.timestamp) as date,
    do.object_class,
    COUNT(*) as count,
    AVG(do.confidence) as avg_confidence
FROM detected_objects do
JOIN frame_detections fd ON do.frame_detection_id = fd.id
JOIN sources s ON fd.source_id = s.id
JOIN models m ON fd.model_id = m.id
GROUP BY s.source_id, m.model_name, DATE(fd.timestamp), do.object_class
ORDER BY date DESC, count DESC;

CREATE UNIQUE INDEX IF NOT EXISTS idx_daily_object_counts_unique
ON daily_object_counts(source_id, model_name, date, object_class);

COMMENT ON MATERIALIZED VIEW daily_object_counts IS '每日对象统计（物化视图，需定期刷新）';

-- 完成
SELECT 'Database initialization completed successfully!' AS status;
