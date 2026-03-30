"""
数据集管理器
负责扫描、索引和采样实验刺激材料
"""

import os
import random
import glob
from typing import List, Dict, Tuple, Optional
from data.models import Session, Patient
import datetime
class DatasetManager:
    """数据集管理器"""

    def __init__(self, dataset_root: str = './dataset'):
        """
        初始化数据集管理器

        Args:
            dataset_root: 数据集根目录
        """
        self.root = dataset_root

        print("=" * 60)
        print("正在扫描数据集...")
        print("=" * 60)

        # 扫描所有数据集
        self.music_data = self._scan_music()
        print(f"✓ 音乐数据集: {self._count_music()} 首")

        self.picture_data = self._scan_pictures()
        total_faces = len(self.picture_data.get('gaped', [])) + len(self.picture_data.get('oasis', []))
        print(f"✓ 面孔图片: {total_faces} 张 (GAPED: {len(self.picture_data['gaped'])}, OASIS: {len(self.picture_data['oasis'])})")

        self.painting_data = self._scan_paintings()
        print(f"✓ 绘画作品: {self._count_paintings()} 张 (流派: {len(self.painting_data)})")

        self.video_data = self._scan_videos()
        total_segments = sum(len(v['segments']) for v in self.video_data)
        print(f"✓ 视频片段: {total_segments} 个 (文件夹: {len(self.video_data)})")

        print("=" * 60)
        print("✓ 数据集扫描完成")
        print("=" * 60 + "\n")

    # ==================== 扫描方法 ====================

    def _scan_music(self) -> list:
        """扫描音乐数据集（兼容新旧目录结构）"""
        tracks = []
        music_root = os.path.join(self.root, 'music')
        if not os.path.isdir(music_root):
            return tracks

        valence_map = {'积极': '正', '正性': '正', '负性': '负', '负': '负'}
        arousal_map = {'高唤醒': '高', '低唤醒': '低'}

        for valence_dir in os.listdir(music_root):
            vdir = os.path.join(music_root, valence_dir)
            if not os.path.isdir(vdir):
                continue
            valence = valence_map.get(valence_dir, valence_dir)
            for arousal_dir in os.listdir(vdir):
                adir = os.path.join(vdir, arousal_dir)
                if not os.path.isdir(adir):
                    continue
                arousal = arousal_map.get(arousal_dir, arousal_dir)
                for f in glob.glob(os.path.join(adir, '*.mp3')):
                    tracks.append({
                        'path': f,
                        'filename': os.path.basename(f),
                        'valence': valence,
                        'arousal': arousal,
                        'group': f"{valence}/{arousal}",
                    })

        if not tracks:
            for f in glob.glob(os.path.join(music_root, '**', '*.mp3'), recursive=True):
                tracks.append({
                    'path': f,
                    'filename': os.path.basename(f),
                    'valence': '',
                    'arousal': '',
                    'group': '',
                })

        return tracks

    def _scan_pictures(self) -> Dict:
        """扫描面孔图片数据集"""
        picture_data = {
            'gaped': [],
            'oasis': []
        }

        # GAPED数据集
        gaped_path = os.path.join(self.root, 'picture/GAPED/GAPED/GAPED/H')
        if os.path.exists(gaped_path):
            for ext in ['*.jpg', '*.jpeg', '*.png', '*.bmp']:
                for file in glob.glob(os.path.join(gaped_path, ext)):
                    picture_data['gaped'].append(file)

        # OASIS数据集
        oasis_path = os.path.join(self.root, 'picture/oasis/face')
        if os.path.exists(oasis_path):
            for ext in ['*.jpg', '*.jpeg', '*.png', '*.bmp']:
                for file in glob.glob(os.path.join(oasis_path, ext)):
                    picture_data['oasis'].append(file)

        return picture_data

    def _scan_paintings(self) -> Dict:
        """扫描绘画数据集（递归查找所有图片目录）"""
        painting_data = {}
        img_exts = {'*.jpg', '*.jpeg', '*.png', '*.bmp', '*.JPG', '*.JPEG', '*.PNG'}

        painting_root = os.path.join(self.root, 'painting')
        if not os.path.isdir(painting_root):
            return painting_data

        print(f"  → 扫描绘画目录: {painting_root}")

        for dirpath, dirnames, filenames in os.walk(painting_root):
            images = []
            for ext in img_exts:
                images.extend(glob.glob(os.path.join(dirpath, ext)))
            if not images:
                continue

            style = os.path.basename(dirpath)
            print(f"  → 找到: {style} ({len(images)} 张)")
            painting_data[style] = [
                {
                    'path': f,
                    'filename': os.path.basename(f),
                    'style': style,
                }
                for f in images
            ]

        return painting_data

    def _scan_videos(self) -> List[Dict]:
        """扫描视频数据集"""
        video_data = []

        sims_path = os.path.join(self.root, 'video/sims/Raw')

        if not os.path.exists(sims_path):
            return video_data

        # 遍历每个视频文件夹
        for video_folder in sorted(os.listdir(sims_path)):
            folder_path = os.path.join(sims_path, video_folder)

            if not os.path.isdir(folder_path):
                continue

            # 扫描该文件夹下的所有视频片段
            segments = []
            for file in os.listdir(folder_path):
                if file.endswith(('.mp4', '.avi', '.mov', '.mkv')):
                    segment_path = os.path.join(folder_path, file)
                    segments.append({
                        'path': segment_path,
                        'filename': file
                    })

            if segments:
                video_data.append({
                    'id': video_folder,
                    'folder_path': folder_path,
                    'segments': segments,
                    'segment_count': len(segments)
                })

        return video_data

    # ==================== 统计方法 ====================

    def _count_music(self) -> int:
        """统计音乐总数"""
        return len(self.music_data)

    def _count_paintings(self) -> int:
        """统计绘画总数"""
        count = 0
        for paintings in self.painting_data.values():
            count += len(paintings)
        return count

    # ==================== 采样方法 ====================

    def sample_music(self, n: int = 6) -> List[Dict]:
        """完全随机采样音乐"""
        all_music = list(self.music_data)
        if len(all_music) < n:
            print(f"⚠ 警告: 音乐总数({len(all_music)})少于请求数量({n})")
            return all_music
        return random.sample(all_music, n)

    def sample_faces(self, n: int = 200) -> List[Dict]:
        """
        随机采样面孔图片

        Args:
            n: 采样数量

        Returns:
            List[Dict]: [
                {
                    'path': '图片路径',
                    'dataset': 'gaped' 或 'oasis'
                },
                ...
            ]
        """
        # 合并两个数据集
        all_faces = []

        for face in self.picture_data['gaped']:
            all_faces.append({
                'path': face,
                'dataset': 'gaped'
            })

        for face in self.picture_data['oasis']:
            all_faces.append({
                'path': face,
                'dataset': 'oasis'
            })

        # 随机采样
        if len(all_faces) < n:
            print(f"⚠ 警告: 面孔总数({len(all_faces)})少于请求数量({n})")
            return all_faces

        return random.sample(all_faces, n)

    def load_classified_images(self, category: str) -> List[str]:
        """
        加载已分类的刺激图片路径列表。

        category 取值：
            'neutral'      — 中性图片（Valence 4.5~5.5）
            'stimulus_neg' — 负性刺激图片（Valence ≤ 3.5）
            'stimulus_pos' — 正性刺激图片（Valence ≥ 6.5）

        Returns:
            图片绝对路径列表
        """
        folder = os.path.join(self.root, 'picture', 'Stimulation', 'classified', category)
        if not os.path.isdir(folder):
            print(f"  [DatasetManager] 分类目录不存在：{folder}")
            return []
        exts = {'.jpg', '.jpeg', '.png', '.bmp'}
        paths = [
            os.path.join(folder, f)
            for f in os.listdir(folder)
            if os.path.splitext(f.lower())[1] in exts
        ]
        print(f"  [DatasetManager] 已分类图片 [{category}]：{len(paths)} 张")
        return paths

    def sample_face_pairs_for_dotprobe(self, n_trials: int = 200) -> List[Tuple[Dict, Dict]]:
        """
        为Dot-probe任务采样面孔配对

        Args:
            n_trials: 试次数量

        Returns:
            List[Tuple]: [
                (face1_dict, face2_dict),  # 试次1
                (face3_dict, face4_dict),  # 试次2
                ...
            ]
        """
        # 需要 n_trials * 2 张面孔
        faces = self.sample_faces(n_trials * 2)

        # 配对
        pairs = []
        for i in range(0, len(faces), 2):
            if i + 1 < len(faces):
                pairs.append((faces[i], faces[i + 1]))

        return pairs

    def sample_paintings(self, n: int = 30) -> List[Dict]:
        """
        完全随机采样绘画

        Args:
            n: 采样数量

        Returns:
            List[Dict]: [
                {
                    'path': '绘画路径',
                    'style': '流派',
                    'filename': '文件名'
                },
                ...
            ]
        """
        # 收集所有绘画
        all_paintings = []

        for style, paintings in self.painting_data.items():
            for painting in paintings:
                all_paintings.append({
                    'path': painting['path'],
                    'style': painting['style'],
                    'filename': painting['filename']
                })

        # 完全随机采样
        if len(all_paintings) < n:
            print(f"⚠ 警告: 绘画总数({len(all_paintings)})少于请求数量({n})")
            return all_paintings

        return random.sample(all_paintings, n)

    def sample_videos(self, n: int = 1, strategy: str = 'single_segment') -> List[Dict]:
        """
        采样视频片段

        Args:
            n: 采样数量
            strategy:
                - 'single_segment': 随机采样n个片段
                - 'full_folder': 随机采样n个文件夹（包含所有片段）

        Returns:
            如果strategy='single_segment':
                List[Dict]: [
                    {
                        'path': '视频片段路径',
                        'filename': '文件名',
                        'parent_folder': '所属文件夹'
                    },
                    ...
                ]

            如果strategy='full_folder':
                List[Dict]: [
                    {
                        'folder': '文件夹名',
                        'folder_path': '文件夹路径',
                        'segments': [
                            {'path': '...', 'filename': '...'},
                            ...
                        ]
                    },
                    ...
                ]
        """
        if strategy == 'single_segment':
            # 从所有片段中随机抽取
            all_segments = []

            for video in self.video_data:
                for segment in video['segments']:
                    all_segments.append({
                        'path': segment['path'],
                        'filename': segment['filename'],
                        'parent_folder': video['id']
                    })

            if len(all_segments) < n:
                print(f"⚠ 警告: 视频片段总数({len(all_segments)})少于请求数量({n})")
                return all_segments

            return random.sample(all_segments, n)

        elif strategy == 'full_folder':
            # 随机选择文件夹
            if len(self.video_data) < n:
                print(f"⚠ 警告: 视频文件夹数({len(self.video_data)})少于请求数量({n})")
                selected = self.video_data
            else:
                selected = random.sample(self.video_data, n)

            result = []
            for folder in selected:
                result.append({
                    'folder': folder['id'],
                    'folder_path': folder['folder_path'],
                    'segments': folder['segments']
                })

            return result

        else:
            raise ValueError(f"未知的采样策略: {strategy}")

    # ==================== 工具方法 ====================

    def get_statistics(self) -> Dict:
        """获取数据集统计信息"""
        stats = {
            'music': {
                'total': self._count_music(),
            },
            'faces': {
                'total': len(self.picture_data['gaped']) + len(self.picture_data['oasis']),
                'gaped': len(self.picture_data['gaped']),
                'oasis': len(self.picture_data['oasis'])
            },
            'paintings': {
                'total': self._count_paintings(),
                'styles': {
                    style: len(paintings)
                    for style, paintings in self.painting_data.items()
                }
            },
            'videos': {
                'total_folders': len(self.video_data),
                'total_segments': sum(len(v['segments']) for v in self.video_data)
            }
        }

        return stats

    def get_patient_by_id(self, patient_id: str) -> Optional[Patient]:
        """
        根据ID获取患者信息

        Args:
            patient_id: 患者ID

        Returns:
            Patient对象 或 None
        """
        try:
            self.cursor.execute("""
                SELECT patient_id, name, age, gender, diagnosis, notes, created_at
                FROM patients
                WHERE patient_id = ?
            """, (patient_id,))

            row = self.cursor.fetchone()

            if row:
                patient = Patient(
                    patient_id=row[0],
                    name=row[1],
                    age=row[2],
                    gender=row[3],
                    diagnosis=row[4],
                    notes=row[5],
                    created_at=datetime.fromisoformat(row[6]) if row[6] else None
                )
                self.logger.info(f"查询到患者: {patient.name} (ID: {patient_id})")
                return patient
            else:
                self.logger.warning(f"未找到患者 (ID: {patient_id})")
                return None

        except Exception as e:
            self.logger.error(f"获取患者失败 (ID: {patient_id}): {e}")
            import traceback
            traceback.print_exc()
            return None

    def get_session_by_id(self, session_id: int) -> Optional[Session]:
        """
        根据ID获取会话

        Args:
            session_id: 会话ID

        Returns:
            Session对象 或 None
        """
        try:
            self.cursor.execute("""
                SELECT session_id, patient_id, session_name, session_date, duration,
                       data_path, has_shimmer, has_video, has_audio,
                       quality_score, notes, created_at
                FROM sessions
                WHERE session_id = ?
            """, (session_id,))

            row = self.cursor.fetchone()

            if row:
                return Session(
                    session_id=row[0],
                    patient_id=row[1],
                    session_name=row[2],
                    session_date=datetime.fromisoformat(row[3]),
                    duration=row[4],
                    data_path=row[5],
                    has_shimmer=bool(row[6]),
                    has_video=bool(row[7]),
                    has_audio=bool(row[8]),
                    quality_score=row[9],
                    notes=row[10],
                    created_at=datetime.fromisoformat(row[11]) if row[11] else None
                )

            return None

        except Exception as e:
            self.logger.error(f"获取会话失败 (ID: {session_id}): {e}")
            return None

# ==================== 测试代码 ====================
if __name__ == '__main__':
    # 初始化
    manager = DatasetManager('./dataset')

    # 打印统计信息
    stats = manager.get_statistics()
    print("\n数据集详细统计:")
    print(f"  音乐: {stats['music']['total']} 首")
    print(f"    - Deam: {stats['music']['deam']}")
    print(f"    - Emotify:")
    for genre, count in stats['music']['emotify'].items():
        print(f"      · {genre}: {count}")

    print(f"\n  面孔: {stats['faces']['total']} 张")
    print(f"    - GAPED: {stats['faces']['gaped']}")
    print(f"    - OASIS: {stats['faces']['oasis']}")

    print(f"\n  绘画: {stats['paintings']['total']} 张")
    print(f"    - 流派数: {len(stats['paintings']['styles'])}")

    print(f"\n  视频: {stats['videos']['total_segments']} 个片段")
    print(f"    - 文件夹数: {stats['videos']['total_folders']}")

    # 测试采样
    print("\n" + "=" * 60)
    print("测试采样功能")
    print("=" * 60)

    print("\n1. 采样6首音乐:")
    music_samples = manager.sample_music(6)
    for i, music in enumerate(music_samples, 1):
        print(f"  {i}. {music['filename']} ({music['dataset']}, {music['genre']})")

    print("\n2. 采样30张绘画:")
    painting_samples = manager.sample_paintings(30)
    for i, painting in enumerate(painting_samples[:5], 1):  # 只显示前5个
        print(f"  {i}. {painting['filename']} ({painting['style']})")
    print(f"  ... 共{len(painting_samples)}张")

    print("\n3. 采样1个视频片段:")
    video_samples = manager.sample_videos(1, strategy='single_segment')
    for video in video_samples:
        print(f"  - {video['filename']} (来自 {video['parent_folder']})")

    print("\n✓ 测试完成")

_global_dataset_manager = None


def get_dataset_manager(root: str = './dataset'):
    """
    获取全局 DatasetManager 单例

    Args:
        root: 数据集根目录

    Returns:
        DatasetManager 实例
    """
    global _global_dataset_manager

    if _global_dataset_manager is None:
        print("\n[DatasetManager] 首次初始化，扫描数据集...")
        _global_dataset_manager = DatasetManager(root)
    else:
        print("[DatasetManager] 使用已缓存的数据集实例")

    return _global_dataset_manager
