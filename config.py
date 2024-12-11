TASK_TNTERVAL = 300  # 抓取数据的时间间隔（秒）
MAX_TRY_TIMES = 5  # 发送邮件的最大重试次数
# 缓存（用于去重）配置
CACHE_SIZE = 500  # 内容缓存条数(用于查重)
CACHE_LOCAL_PATH = "msg_cache.pkl"  # 本地缓存路径
# 抓取结果发送的远程服务器的服务链接
POST_URL = "http://cpts-chn-slb-zj-2.bocomm.com/CPTS.CPTS-EDPS.V-1.0/nesAIQryCesDscntInfo.bocom?"
# POST_URL = "https://abs.bankcomm.com/cptsdk/CPTS.CPTS-EDPS.V-1.0/nesAIQryCesDscntInfo.ajax?"