# -*- coding: utf-8 -*-
# @file env.py
# @brief The Environment Variables Reader
# @author sailing-innocent
# @date 2025-04-21
# @version 1.0
# ---------------------------------
import dotenv 

def read_env(mode='dev'):
    # read .env.dev file or .env.prod file
    if mode == 'dev':
        env_file = '.env.dev'
    elif mode == 'debug':
        env_file = '.env.debug'
    elif mode == 'prod':
        env_file = '.env.prod'
    else:
        raise ValueError('mode must be dev or prod')

    print(f"Loading environment variables from {env_file}")
    # 明确指定 UTF-8 编码，避免 Windows 系统默认使用 GBK 导致的解析错误
    dotenv.load_dotenv(env_file, encoding='utf-8')
