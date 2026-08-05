"""拼音检测 — 基于拼音音节词典的全切分判定（best-effort，无第三方依赖）。

判定逻辑：token 能被完整切分为合法拼音音节 → 判为拼音。
由于英文词（monthly/order/amount 等）无法完整切分为拼音音节，不会被误判。
真实中文拼音缩写（tongji/jine/yueding 等）可被正确识别。
"""

from __future__ import annotations

# 标准汉语拼音音节（无声调），覆盖常用组合。
_PINYIN_SYLLABLES = {
    "a", "o", "e", "i", "u", "ü", "yu", "er",
    "ai", "ei", "ao", "ou", "an", "en", "ang", "eng", "ong",
    "ia", "ie", "iao", "iu", "ian", "in", "iang", "ing", "iong",
    "ua", "uo", "uai", "ui", "uan", "un", "uang", "ueng", "üe", "üan", "ün",
    "ba", "bo", "bai", "bei", "bao", "ban", "ben", "bang", "beng", "bi", "bie", "biao", "bian", "bin", "bing", "bu",
    "pa", "po", "pai", "pei", "pao", "pou", "pan", "pen", "pang", "peng", "pi", "pie", "piao", "pian", "pin", "ping", "pu",
    "ma", "mo", "me", "mai", "mei", "mao", "mou", "man", "men", "mang", "meng", "mi", "mie", "miao", "miu", "mian", "min", "ming", "mu",
    "fa", "fo", "fei", "fou", "fan", "fen", "fang", "feng", "fu",
    "da", "de", "dai", "dao", "dou", "dan", "den", "dang", "deng", "di", "die", "diao", "diu", "dian", "ding", "dong", "du", "duan", "dun",
    "ta", "te", "tai", "tao", "tou", "tan", "tang", "teng", "ti", "tie", "tiao", "tian", "ting", "tong", "tu", "tuan", "tun",
    "na", "nai", "nei", "nao", "nou", "nan", "nen", "nang", "neng", "ni", "nie", "niao", "niu", "nian", "nin", "ning", "nong", "nu", "nü", "nuan", "nüe",
    "la", "le", "lai", "lei", "lao", "lou", "lan", "lang", "leng", "li", "lia", "lie", "liao", "liu", "lian", "lin", "liang", "ling", "long", "lu", "lü", "luan", "lun", "luo", "lüe",
    "ga", "ge", "gai", "gao", "gou", "gan", "gen", "gang", "geng", "gong", "gu", "gua", "guo", "guai", "gui", "guan", "gun", "guang",
    "ka", "ke", "kai", "kao", "kou", "kan", "ken", "kang", "keng", "kong", "ku", "kua", "kuo", "kuai", "kui", "kuan", "kun", "kuang",
    "ha", "he", "hai", "hei", "hao", "hou", "han", "hen", "hang", "heng", "hong", "hu", "hua", "huo", "huai", "hui", "huan", "hun", "huang",
    "ji", "jia", "jie", "jiao", "jiu", "jian", "jin", "jiang", "jing", "jiong", "ju", "jue", "juan", "jun",
    "qi", "qia", "qie", "qiao", "qiu", "qian", "qin", "qiang", "qing", "qiong", "qu", "que", "quan", "qun",
    "xi", "xia", "xie", "xiao", "xiu", "xian", "xin", "xiang", "xing", "xiong", "xu", "xue", "xuan", "xun",
    "zha", "zhe", "zhi", "zhai", "zhao", "zhou", "zhan", "zhen", "zhang", "zheng", "zhong", "zhu", "zhua", "zhuo", "zhuai", "zhui", "zhuan", "zhun", "zhuang",
    "cha", "che", "chi", "chai", "chao", "chou", "chan", "chen", "chang", "cheng", "chong", "chu", "chuo", "chuai", "chui", "chuan", "chun", "chuang",
    "sha", "she", "shi", "shai", "shao", "shou", "shan", "shen", "shang", "sheng", "shu", "shua", "shuo", "shuai", "shui", "shuan", "shun", "shuang",
    "ra", "re", "ri", "rao", "rou", "ran", "ren", "rang", "reng", "rong", "ru", "ruo", "rui", "ruan", "run",
    "za", "ze", "zi", "zai", "zao", "zou", "zan", "zen", "zang", "zeng", "zong", "zu", "zuan", "zun", "zuo",
    "ca", "ce", "ci", "cai", "cao", "cou", "can", "cen", "cang", "ceng", "cong", "cu", "cuan", "cun", "cuo",
    "sa", "se", "si", "sai", "sao", "sou", "san", "sen", "sang", "seng", "song", "su", "suan", "sun", "suo",
    "ya", "ye", "yao", "you", "yan", "yang", "yue", "yuan", "yun", "yong", "yi", "yin", "ying",
    "wa", "wo", "wai", "wei", "wao", "wen", "wang", "weng", "wu",
}

_MAX_SYL = 6  # 最长音节长度（如 zhuang）


def _segment_pinyin(token: str) -> bool:
    """贪心最长匹配：token 能否完整切分为拼音音节。"""
    i = 0
    n = len(token)
    while i < n:
        matched = False
        for length in range(min(_MAX_SYL, n - i), 0, -1):
            if token[i : i + length] in _PINYIN_SYLLABLES:
                i += length
                matched = True
                break
        if not matched:
            return False
    return True


def is_pinyin_token(token: str, root_en_set: set[str]) -> bool:
    """判断 token 是否为拼音（非英文词根）。"""
    t = token.strip().lower()
    if not t or t in root_en_set:
        return False
    if not t.isalpha():
        return False
    if len(t) > 12:
        return False
    return _segment_pinyin(t)
