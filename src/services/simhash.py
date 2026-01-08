"""
SimHash 文本相似度计算
用于高效的大规模文本去重和聚类
"""

import hashlib
import math
import re
from collections import defaultdict
from typing import Any


class SimHash:
    """
    SimHash 算法实现
    用于快速计算文本相似度
    """

    def __init__(
        self,
        hash_bits: int = 64,
        token_type: str = 'word',
    ) -> None:
        """
        初始化 SimHash

        Args:
            hash_bits: 哈希位数（32, 64, 128）
            token_type: 分词类型 ('word' 或 'char')
        """
        self.hash_bits = hash_bits
        self.token_type = token_type
        self.hash_mask = (1 << hash_bits) - 1

    def tokenize(self, text: str) -> list[str]:
        """
        分词

        Args:
            text: 输入文本

        Returns:
            词汇列表
        """
        if not text:
            return []

        # 转小写
        text = text.lower()

        # 移除标点和特殊字符
        text = re.sub(r'[^\w\s\u4e00-\u9fff]', ' ', text)

        if self.token_type == 'word':
            # 按词分词（空格分隔，中文按字符）
            words = []
            for part in text.split():
                if '\u4e00' <= part <= '\u9fff':
                    # 中文，按字符分割
                    words.extend(list(part))
                else:
                    # 英文等，按空格分割
                    words.extend(part.split())
            return words

        else:  # char
            # 按字符分词
            return list(text.replace(' ', ''))

    def compute_hash(self, text: str) -> int:
        """
        计算 SimHash 值

        Args:
            text: 输入文本

        Returns:
            SimHash 值（整数）
        """
        tokens = self.tokenize(text)

        if not tokens:
            return 0

        # 初始化权重向量
        weights = [0] * self.hash_bits

        # 计算每个 token 的哈希并累加权重
        for token in tokens:
            # 使用 SHA256 哈希
            token_hash = hashlib.sha256(token.encode('utf-8')).hexdigest()
            # 取前 hash_bits 位
            hash_int = int(token_hash[: self.hash_bits // 4], 16)

            # 根据哈希值的每一位更新权重
            for i in range(self.hash_bits):
                if (hash_int >> i) & 1:
                    weights[i] += 1
                else:
                    weights[i] -= 1

        # 生成最终哈希值
        simhash = 0
        for i in range(self.hash_bits):
            if weights[i] >= 0:
                simhash |= (1 << i)

        return simhash

    def compute_hash_weighted(
        self,
        text: str,
        weights: dict[str, float] | None = None,
    ) -> int:
        """
        计算加权 SimHash 值
        可以为不同的 token 分配不同的权重

        Args:
            text: 输入文本
            weights: token 权重字典

        Returns:
            SimHash 值（整数）
        """
        tokens = self.tokenize(text)

        if not tokens:
            return 0

        # 初始化权重向量
        weight_vectors = [0] * self.hash_bits

        # 统计 token 频率
        token_freq = defaultdict(int)
        for token in tokens:
            token_freq[token] += 1

        # 计算加权哈希
        for token, freq in token_freq.items():
            # 使用 SHA256 哈希
            token_hash = hashlib.sha256(token.encode('utf-8')).hexdigest()
            hash_int = int(token_hash[: self.hash_bits // 4], 16)

            # 获取权重（频率 × 额外权重）
            weight = freq
            if weights and token in weights:
                weight *= weights[token]

            # 更新权重向量
            for i in range(self.hash_bits):
                if (hash_int >> i) & 1:
                    weight_vectors[i] += weight
                else:
                    weight_vectors[i] -= weight

        # 生成最终哈希值
        simhash = 0
        for i in range(self.hash_bits):
            if weight_vectors[i] >= 0:
                simhash |= (1 << i)

        return simhash

    def hamming_distance(self, hash1: int, hash2: int) -> int:
        """
        计算汉明距离

        Args:
            hash1: 第一个哈希值
            hash2: 第二个哈希值

        Returns:
            汉明距离
        """
        x = hash1 ^ hash2
        distance = 0
        while x:
            distance += 1
            x &= x - 1
        return distance

    def similarity(self, hash1: int, hash2: int) -> float:
        """
        计算相似度（0-1）

        Args:
            hash1: 第一个哈希值
            hash2: 第二个哈希值

        Returns:
            相似度（0=完全不同，1=完全相同）
        """
        distance = self.hamming_distance(hash1, hash2)
        max_distance = self.hash_bits
        return 1.0 - (distance / max_distance)

    def is_duplicate(
        self,
        hash1: int,
        hash2: int,
        threshold: float = 0.85,
    ) -> bool:
        """
        判断两个哈希值是否相似

        Args:
            hash1: 第一个哈希值
            hash2: 第二个哈希值
            threshold: 相似度阈值

        Returns:
            是否相似
        """
        return self.similarity(hash1, hash2) >= threshold


class TextCluster:
    """
    文本聚类器
    使用 SimHash 进行高效的文本聚类和去重
    """

    def __init__(
        self,
        simhash_bits: int = 64,
        similarity_threshold: float = 0.85,
        token_type: str = 'word',
    ) -> None:
        """
        初始化聚类器

        Args:
            simhash_bits: SimHash 位数
            similarity_threshold: 相似度阈值
            token_type: 分词类型
        """
        self.simhash = SimHash(hash_bits=simhash_bits, token_type=token_type)
        self.similarity_threshold = similarity_threshold

    def compute_hash(self, text: str) -> int:
        """计算文本的 SimHash"""
        return self.simhash.compute_hash(text)

    def cluster_texts(
        self,
        texts: list[str],
        ids: list[int] | None = None,
    ) -> dict[int, list[int]]:
        """
        对文本进行聚类

        Args:
            texts: 文本列表
            ids: 对应的 ID 列表

        Returns:
            聚类结果：{代表 ID: [相似 ID 列表]}
        """
        if not texts:
            return {}

        if ids is None:
            ids = list(range(len(texts)))

        if len(texts) != len(ids):
            raise ValueError("texts and ids must have the same length")

        # 计算所有哈希值
        hashes = [self.compute_hash(text) for text in texts]

        # 聚类结果
        clusters: dict[int, list[int]] = {}
        assigned = set()

        for i, (text_id, text_hash) in enumerate(zip(ids, hashes)):
            if text_id in assigned:
                continue

            # 创建新簇
            clusters[text_id] = []
            assigned.add(text_id)

            # 查找相似文本
            for j, (other_id, other_hash) in enumerate(zip(ids, hashes)):
                if i == j or other_id in assigned:
                    continue

                if self.simhash.is_duplicate(text_hash, other_hash, self.similarity_threshold):
                    clusters[text_id].append(other_id)
                    assigned.add(other_id)

        return clusters

    def find_duplicates(
        self,
        texts: list[str],
        ids: list[int] | None = None,
    ) -> list[tuple[int, int, float]]:
        """
        查找重复的文本对

        Args:
            texts: 文本列表
            ids: 对应的 ID 列表

        Returns:
            重复对列表：[(id1, id2, similarity), ...]
        """
        if not texts:
            return []

        if ids is None:
            ids = list(range(len(texts)))

        # 计算所有哈希值
        hashes = [self.compute_hash(text) for text in texts]

        # 查找重复对
        duplicates = []

        for i in range(len(hashes)):
            for j in range(i + 1, len(hashes)):
                similarity = self.simhash.similarity(hashes[i], hashes[j])
                if similarity >= self.similarity_threshold:
                    duplicates.append((ids[i], ids[j], similarity))

        # 按相似度排序
        duplicates.sort(key=lambda x: x[2], reverse=True)

        return duplicates

    def find_nearest(
        self,
        query: str,
        candidates: list[str],
        candidate_ids: list[int] | None = None,
        top_k: int = 5,
    ) -> list[tuple[int, float]]:
        """
        查找与查询文本最相似的候选文本

        Args:
            query: 查询文本
            candidates: 候选文本列表
            candidate_ids: 候选 ID 列表
            top_k: 返回前 k 个结果

        Returns:
            相似度列表：[(id, similarity), ...]
        """
        if not candidates:
            return []

        if candidate_ids is None:
            candidate_ids = list(range(len(candidates)))

        # 计算查询哈希
        query_hash = self.compute_hash(query)

        # 计算所有候选的相似度
        similarities = []
        for candidate, cand_id in zip(candidates, candidate_ids):
            cand_hash = self.compute_hash(candidate)
            sim = self.simhash.similarity(query_hash, cand_hash)
            similarities.append((cand_id, sim))

        # 排序并返回前 k 个
        similarities.sort(key=lambda x: x[1], reverse=True)
        return similarities[:top_k]


def compute_content_hash(content: str | None) -> str | None:
    """
    计算内容的 SHA256 哈希
    用于检测内容变化

    Args:
        content: 文本内容

    Returns:
        十六进制哈希字符串
    """
    if not content:
        return None

    # 标准化内容（去除空格、换行等）
    normalized = re.sub(r'\s+', ' ', content.strip())

    return hashlib.sha256(normalized.encode('utf-8')).hexdigest()


def text_similarity_simple(text1: str, text2: str) -> float:
    """
    简单的文本相似度计算（词汇重叠）
    作为 SimHash 的补充

    Args:
        text1: 第一个文本
        text2: 第二个文本

    Returns:
        相似度（0-1）
    """
    # 标准化
    text1 = re.sub(r'[^\w\s\u4e00-\u9fff]', ' ', text1.lower())
    text2 = re.sub(r'[^\w\s\u4e00-\u9fff]', ' ', text2.lower())

    # 分词
    words1 = set(text1.split())
    words2 = set(text2.split())

    if not words1 or not words2:
        return 0.0

    # Jaccard 相似度
    intersection = len(words1 & words2)
    union = len(words1 | words2)

    return intersection / union if union > 0 else 0.0
