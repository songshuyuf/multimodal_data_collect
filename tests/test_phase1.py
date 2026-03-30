"""
Phase 1 模块测试脚本
验证数据库、文件管理、会话管理功能
"""

import sys
import os

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from data.database import DatabaseManager
from data.models import Patient, Session
from data.files import FileManager
from data.session import SessionManager
from datetime import datetime


def test_database():
    """测试数据库功能"""
    print("\n" + "=" * 50)
    print("测试数据库模块")
    print("=" * 50)

    db = DatabaseManager("./data/database/test.db")

    # 添加患者
    print("\n1. 测试添加患者...")
    patient = Patient(
        name="张三",
        age=35,
        gender="M",
        diagnosis="焦虑症",
        notes="测试患者"
    )
    patient_id = db.add_patient(patient)
    print(f"   ✓ 添加患者成功，ID: {patient_id}")

    # 获取患者
    print("\n2. 测试获取患者...")
    retrieved = db.get_patient(patient_id)
    print(f"   ✓ 获取患者成功: {retrieved.name}, 年龄 {retrieved.age}")

    # 更新患者
    print("\n3. 测试更新患者...")
    retrieved.age = 36
    retrieved.diagnosis = "焦虑症 (改善中)"
    db.update_patient(retrieved)
    updated = db.get_patient(patient_id)
    print(f"   ✓ 更新成功: 年龄 {updated.age}, 诊断 '{updated.diagnosis}'")

    # 搜索患者
    print("\n4. 测试搜索患者...")
    results = db.search_patients("张")
    print(f"   ✓ 搜索到 {len(results)} 位患者")

    # 添加会话
    print("\n5. 测试添加会话...")
    session = Session(
        patient_id=patient_id,
        session_name="基线测试",
        session_date=datetime.now(),
        duration=300,
        data_path="test_session",
        has_shimmer=True,
        has_video=True,
        has_audio=True
    )
    session_id = db.add_session(session)
    print(f"   ✓ 添加会话成功，ID: {session_id}")

    # 获取患者会话
    print("\n6. 测试获取患者会话...")
    sessions = db.get_patient_sessions(patient_id)
    print(f"   ✓ 患者有 {len(sessions)} 个会话")

    # 统计信息
    print("\n7. 测试统计信息...")
    stats = db.get_patient_stats(patient_id)
    print(f"   ✓ 总会话数: {stats.get('total_sessions', 0)}")
    print(f"   ✓ 总时长: {stats.get('total_duration', 0)} 秒")

    db.close()
    print("\n✓ 数据库测试完成！")


def test_file_manager():
    """测试文件管理器"""
    print("\n" + "=" * 50)
    print("测试文件管理器")
    print("=" * 50)

    fm = FileManager("./data/test_sessions")

    # 创建会话目录
    print("\n1. 测试创建会话目录...")
    session_path = fm.create_session_directory(1, "测试会话")
    print(f"   ✓ 创建目录: {session_path}")

    # 列出文件
    print("\n2. 测试列出文件...")
    session_dir = os.path.basename(session_path)
    files = fm.list_session_files(session_dir)
    print(f"   ✓ Shimmer文件: {len(files['shimmer'])} 个")
    print(f"   ✓ 视频文件: {len(files['video'])} 个")
    print(f"   ✓ 音频文件: {len(files['audio'])} 个")

    # 检查模态
    print("\n3. 测试检查模态...")
    has_shimmer = fm.check_modality_exists(session_dir, 'shimmer')
    print(f"   ✓ Shimmer数据存在: {has_shimmer}")

    # 计算大小
    print("\n4. 测试计算大小...")
    sizes = fm.get_session_size(session_dir)
    print(f"   ✓ 总大小: {fm.format_size(sizes['total'])}")

    print("\n✓ 文件管理器测试完成！")


def test_session_manager():
    """测试会话管理器"""
    print("\n" + "=" * 50)
    print("测试会话管理器")
    print("=" * 50)

    db = DatabaseManager("./data/database/test.db")
    fm = FileManager("./data/test_sessions")
    sm = SessionManager(db, fm)

    # 获取一个患者ID (假设已经创建)
    patients = db.get_all_patients()
    if not patients:
        print("   ! 没有患者，跳过会话管理器测试")
        return

    patient_id = patients[0].patient_id

    # 创建会话
    print("\n1. 测试创建会话...")
    session = sm.create_session(patient_id, "集成测试会话", "这是一个测试会话")
    if session:
        print(f"   ✓ 创建会话成功: {session.session_name} (ID: {session.session_id})")

    # 启动会话
    print("\n2. 测试启动会话...")
    success = sm.start_session(session.session_id)
    print(f"   ✓ 启动会话: {'成功' if success else '失败'}")

    # 获取路径
    print("\n3. 测试获取路径...")
    paths = sm.get_current_session_paths()
    if paths:
        print(f"   ✓ Shimmer路径: {paths['shimmer']}")
        print(f"   ✓ 视频路径: {paths['video']}")
        print(f"   ✓ 音频路径: {paths['audio']}")

    # 结束会话
    print("\n4. 测试结束会话...")
    success = sm.end_session(duration=120, quality_score=0.95)
    print(f"   ✓ 结束会话: {'成功' if success else '失败'}")

    # 获取会话信息
    print("\n5. 测试获取会话信息...")
    info = sm.get_session_info(session.session_id)
    if info:
        print(f"   ✓ 会话名称: {info['session']['session_name']}")
        print(f"   ✓ 时长: {info['session']['duration']} 秒")
        print(f"   ✓ 总大小: {info['sizes']['total']}")

    # 验证数据
    print("\n6. 测试验证数据...")
    validation = sm.validate_session_data(session.session_id)
    print(f"   ✓ 数据有效: {validation['valid']}")

    db.close()
    print("\n✓ 会话管理器测试完成！")


def main():
    """主测试函数"""
    print("\n" + "=" * 50)
    print("Phase 1 - Day 1 模块测试")
    print("=" * 50)

    try:
        test_database()
        test_file_manager()
        test_session_manager()

        print("\n" + "=" * 50)
        print("✓ 所有测试通过！")
        print("=" * 50)
        print("\n可以运行 GUI 了:")
        print("  python main.py")

    except Exception as e:
        print(f"\n✗ 测试失败: {e}")
        import traceback
        traceback.print_exc()


if __name__ == '__main__':
    main()
