# -*- coding: utf-8 -*-
import time

import requests, re, os, shutil, subprocess
from multiprocessing import Pool, Manager

URL_SRC_PARTS = "https://usher.ttvnw.net/vod/%s.m3u8?nauthsig=%s&nauth=%s&allow_source=true&player=twitchweb&allow_spectre=true&allow_audio_only=true"
URL_GET_TOKEN = "https://api.twitch.tv/api/vods/%s/access_token"
CLIENT_ID = "jzkbprff40iqj646a697cyrvl0zt2m6"
TMP_DIR = 'tmp'

def record_file(name, content, bin=False):
    file = None
    if bin:
        file = open(name, "wb+")
    else:
        file = open(name, "w+")
    file.write(content)
    file.close()


def parse_m3u(data):
    regex_resolution = re.compile(r"([0-9]+p[0-9]|chunked)+")
    lines = data.split("\n")
    i = 0
    result = {}
    while i < len(lines):
        if lines[i][:17] == '#EXT-X-STREAM-INF':
            data = lines[i].split(',')
            resolution = data[len(data) - 1][7:-1]
            if regex_resolution.match(resolution):
                if resolution == 'chunked':
                    result['source'] = lines[i + 1]
                else:
                    result[resolution] = lines[i + 1]
        i += 1
    return result


def extract_parts(data, url):
    lines = data.split("\n")
    url_splited = url.split('/')
    url = '/'.join(url_splited[:-1]) + '/'
    i = 0
    result = []
    while i < len(lines):
        if lines[i][:7] == '#EXTINF':
            result.append(url + lines[i + 1])
        i += 1
    return result


def get_video(link):
    print(link)
    r = requests.get(link)
    record_file(os.path.join(os.getcwd(), TMP_DIR, str(link.split('/')[-1])), r.content, True)


if __name__ == "__main__":
    process = input("사용할 프로세스 개수를 입력하세요: ")
    vod_id = input("VOD ID를 입력하세요: ")
    print("\nGETTING TOKEN FROM AUTHORIZATION\n")
    parsed_URL_Token = URL_GET_TOKEN % vod_id
    r = requests.get(parsed_URL_Token, headers={"Client-ID": CLIENT_ID})
    if r.status_code != 200:
        print("Failed to get authorization token")
        exit()

    auth = r.json()

    print("SEEKING VOD INFORMATION\n")

    parsed_URL_list = URL_SRC_PARTS % (vod_id, auth['sig'], auth['token'])

    r = requests.get(parsed_URL_list, headers={"Client-ID": CLIENT_ID})

    list_solutions = parse_m3u(r.text)

    if len(list_solutions) <= 0:
        print('Unable to obtain information about this VOD')
        exit()

    choice = ''
    url = ''
    while not (choice in list_solutions.keys()):
        print("Choose one of the following resolutions:\n")
        for resolution in list_solutions:
            print('> ' + resolution)
        choice = input("\nWrite your choice: ")

        try:
            url = list_solutions[choice]
        except KeyError:
            print("\nInvalid option\n")

    print("\nDOWNLOADING VOD PARTS LIST\n")

    r = requests.get(url)

    parts = extract_parts(r.text, url)

    print(str(len(parts)) + ' parts.')

    print("\nINITIATING DOWNLOAD\n")

    if not os.path.isdir(TMP_DIR):
        os.mkdir(TMP_DIR)
    start_time = time.time()
    pool = Pool(processes=int(process))
    pool.map(get_video, parts)
    print("--- %s seconds ---" % (time.time() - start_time))

    print("\nJOINING PARTS\n")

    list_em_texto = open('list_parts.tmp', "w+")
    list_files = os.listdir(TMP_DIR)
    list_files.sort(key=lambda x: int(x.split('.')[0]))
    for file in list_files:
        list_em_texto.write("file '" + os.path.join(TMP_DIR, file) + "'\n")
    list_em_texto.close()

    subprocess.run(["ffmpeg", "-f", "concat", "-safe", "0", "-i", "list_parts.tmp", "-c", "copy", "%s.mp4" % vod_id])

    #shutil.rmtree(os.path.join(os.getcwd(), "tmp"), ignore_errors=True)

    #os.remove("list_parts.tmp")

    print("\n> COMPLETED <\n")
