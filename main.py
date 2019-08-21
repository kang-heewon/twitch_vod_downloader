import shutil
import sys
import ffmpeg
import os
import re
import requests
from PyQt5.QtCore import QRunnable, pyqtSlot, QThreadPool, QObject, pyqtSignal
from PyQt5.QtGui import QTextCursor
from PyQt5.QtWidgets import QApplication, QWidget, QPushButton, QVBoxLayout, QLineEdit, QTextEdit, QGroupBox, QLabel, \
    QGridLayout, QComboBox, QDesktopWidget

URL_SRC_PARTS = "https://usher.ttvnw.net/vod/%s.m3u8?nauthsig=%s&nauth=%s&allow_source=true&player=twitchweb&allow_spectre=true&allow_audio_only=true"
URL_GET_TOKEN = "https://api.twitch.tv/api/vods/%s/access_token"
CLIENT_ID = "jzkbprff40iqj646a697cyrvl0zt2m6"
TMP_DIR = 'tmp'


class MyApp(QWidget):

    def __init__(self):
        super().__init__()
        self.initUI()

    def initUI(self):
        self.threadpool = QThreadPool()

        self.text = QTextEdit()
        self.text.setAcceptRichText(False)
        self.text.isReadOnly()
        btn1 = QPushButton('&Download', self)
        btn1.toggle()
        btn1.clicked.connect(self.download_handler)
        self.text.textChanged.connect(self.text_changed)

        self.download_group = QGroupBox('download')
        self.vod_label = QLabel('Vod:')
        self.vod = QLineEdit(self)
        self.vod.move(60, 100)
        self.resolution_label = QLabel('해상도:')
        self.resolution = QComboBox()
        self.resolution.addItem('source')
        self.resolution.addItem('720p30')
        self.resolution.addItem('480p30')
        self.resolution.addItem('360p30')
        self.resolution.addItem('160p30')
        self.download_layout = QGridLayout()
        self.download_layout.addWidget(self.vod_label, 0, 0)
        self.download_layout.addWidget(self.vod, 0, 1)
        self.download_layout.addWidget(self.resolution_label, 1, 0)
        self.download_layout.addWidget(self.resolution, 1, 1)

        self.download_group.setLayout(self.download_layout)

        self.layout = QVBoxLayout()
        self.layout.addWidget(self.download_group)
        self.layout.addWidget(btn1)
        self.layout.addWidget(self.text)
        self.setLayout(self.layout)

        self.setWindowTitle('twitch downloader')
        self.resize(1000, 500)
        qr = self.frameGeometry()
        cp = QDesktopWidget().availableGeometry().center()
        qr.moveCenter(cp)
        self.move(qr.topLeft())
        self.show()

    def text_changed(self):
        self.text.moveCursor(QTextCursor.End)

    def download_handler(self):
        vod = self.vod.text()
        resolution = self.resolution.currentText()
        parts = self.get_parts(vod, resolution)
        worker = Worker(self.get_video, parts)
        worker.signals.finished.connect(self.thread_complete)
        self.threadpool.start(worker)

    def thread_complete(self):
        vod = self.vod.text()
        self.sum_vod(vod)

    def record_file(self, name, content, bin=False):
        if not os.path.exists('tmp'):
            os.makedirs('tmp')
        file = None
        if bin:
            file = open(name, "wb+")
        else:
            file = open(name, "w+")
        file.write(content)
        file.close()

    def parse_m3u(self, data):
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

    def get_video(self, links):
        for link in links:
            r = requests.get(link)
            self.record_file(os.path.join(os.getcwd(), TMP_DIR, str(link.split('/')[-1])), r.content, True)

    def extract_parts(self, data, url):
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

    def get_parts(self, vod_id, resolution):
        self.text.append('GETTING TOKEN FROM AUTHORIZATION')
        self.text.repaint()
        parsed_URL_Token = URL_GET_TOKEN % vod_id
        r = requests.get(parsed_URL_Token, headers={"Client-ID": CLIENT_ID})
        if r.status_code != 200:
            self.text.append('Failed to get authorization token')
            return
        auth = r.json()

        self.text.append('SEEKING VOD INFORMATION')
        self.text.repaint()
        parsed_URL_list = URL_SRC_PARTS % (vod_id, auth['sig'], auth['token'])

        r = requests.get(parsed_URL_list, headers={"Client-ID": CLIENT_ID})

        list_solutions = self.parse_m3u(r.text)

        if len(list_solutions) <= 0:
            self.text.append('no link')
            self.text.repaint()
            return

        url = list_solutions[resolution]

        self.text.append('DOWNLOADING VOD PARTS LIST')
        self.text.repaint()

        r = requests.get(url)
        parts = self.extract_parts(r.text, url)
        return parts

    def sum_vod(self, vod_id):
        self.text.append('JOINING PARTS')
        self.text.repaint()
        list_em_texto = open('list_parts.tmp', "w+")
        list_files = os.listdir(TMP_DIR)
        list_files.sort(key=lambda x: int(x.split('.')[0]))
        for file in list_files:
            list_em_texto.write("file '" + os.path.join(TMP_DIR, file) + "'\n")
        list_em_texto.close()
        stream = ffmpeg.input('list_parts.tmp', format='concat', safe=0)
        stream = ffmpeg.output(stream, vod_id+'.mp4', codec='copy')
        stream = ffmpeg.overwrite_output(stream)
        ffmpeg.run(stream)
        shutil.rmtree(os.path.join(os.getcwd(), "tmp"), ignore_errors=True)
        os.remove("list_parts.tmp")
        self.text.append('====== COMPLETED ======')
        self.text.repaint()


class Worker(QRunnable):
    def __init__(self, fn, *args, **kwargs):
        super(Worker, self).__init__()
        self.signals = WorkerSignals()
        self.fn = fn
        self.args = args
        self.kwargs = kwargs

    @pyqtSlot()
    def run(self):
        try:
            result = self.fn(*self.args, **self.kwargs)
        except Exception as e:
            print(e)
        finally:
            self.signals.finished.emit()


class WorkerSignals(QObject):
    finished = pyqtSignal()

if __name__ == '__main__':
    app = QApplication(sys.argv)
    ex = MyApp()
    sys.exit(app.exec_())
