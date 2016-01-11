#!/usr/bin/env python3
import mimetypes, os, json, time
from threading import Thread
from sys import argv
from http.server import BaseHTTPRequestHandler, HTTPServer
from sshfetch import *
from pexpect import pxssh

GUI_json = {}
root_dir = os.getcwd() + '/html/'
SSHIP, SSHUser, SSHPw, fetchInterval, SSHConnectAttempts, GUIIP, GUIPort = None, None, None, None, None, None, None

def load_config():
    conF = open('config.json', 'r')
    with open('config.json', 'r') as conF:
        configDict = json.loads(conF.read())
        global SSHIP
        global SSHUser
        global SSHPw
        global GUIIP
        global GUIPort
        global SSHConnectAttempts
        global fetchInterval
        SSHIP, SSHUser, SSHPw = configDict['ssh']['ip'], configDict['ssh']['username'], configDict['ssh']['password']
        SSHConnectAttempts, fetchInterval = configDict['ssh']['connectattempts'], float(configDict['ssh']['fetchinterval'])
        GUIIP, GUIPort = configDict['guiserver']['ip'], configDict['guiserver']['port']
        with open(root_dir+'gui_config.json', 'w') as guiconF:
            guiconF.write(json.dumps({'ajaxlink':'http://'+GUIIP+':'+str(GUIPort)}))

def update_with_commands(commandList):
    ps = pxssh.pxssh()
    global GUI_json
    try:
        for i in range(1, SSHConnectAttempts):
            if ps.login(SSHIP, SSHUser, SSHPw):
                while True:
                    #print(service_list_to_json(execute_commands(ps,commandList)))
                    GUI_json = service_list_to_json(execute_commands(ps,commandList))
                    print(GUI_json)
                    time.sleep(fetchInterval)
        ps.logout()
    except KeyboardInterrupt:
        print('\nSSH pull interrupted, quitting')
        ps.logout()


class GUIHandler(BaseHTTPRequestHandler):
    '''Small class to define HTTP handler of the front end of the GUI'''
    error_message_format = '<h1>404: File not found </h1>'
    
    def do_GET(self):
        mime = {"html":"text/html", "css":"text/css", "png":"image/png", "jpg":"image/jpg", "js":"application/javascript", "json":"application/json"}
        RequestedFileType = mimetypes.guess_type(self.path)[0] if mimetypes.guess_type(self.path)[0]!=None else 'text/html'
        try:
            if self.path == '/':
                self.send_response(200)
                self.send_header("Content-type", "application/json")
                self.end_headers()
                global GUI_json
                #with open('sample_output.txt', 'r') as f: GUI_json = service_list_to_json(f.read().splitlines())
                self.wfile.write(bytes(GUI_json, 'UTF-8'))
                return
            elif os.path.isfile(root_dir + self.path):
                self.send_response(200)
                self.send_header("Content-type", RequestedFileType)
                self.end_headers()
                fp = open(root_dir + self.path, 'rb')
                self.wfile.write(fp.read())
                fp.close()
                return
            else:
                self.send_response(404, 'File not found')
                self.send_header("Content-type", 'text/html')
                self.end_headers()
                self.wfile.write(bytes('File not found', 'UTF-8'))
                return
        except BrokenPipeError:
            print('Failed to complete request')
    
    def log_message(self, format, *args):
        return

if __name__ == '__main__':
    load_config()
    GUIserver = HTTPServer((GUIIP, GUIPort), GUIHandler)
    GUIserverThread = Thread(target=GUIserver.serve_forever)
    try:
        GUIserverThread.start()
        update_with_commands(['nova service-list'])
    except:
        print("\nStopping GUI server and SSH-pulling.")
        #GUIserverThread.join()
