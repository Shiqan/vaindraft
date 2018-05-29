import os
import tornado.ioloop
import tornado.httpserver
import multiprocessing
import unittest
from selenium import webdriver
from selenium.webdriver.firefox.options import Options

from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC

from vaindraft.app import Application


def create_process(port, queue, boot_function, application, processor=multiprocessing):
    p = processor.Process(target=boot_function,  args=(queue, port,  application))
    p.start()
    return p
 
def start_application_server(queue, port, application):
    http_server = tornado.httpserver.HTTPServer(application)
    http_server.listen(port)
    actual_port = port
    if port == 0: # special case, an available port is picked automatically
        # only pick first! (for now)
        assert len(http_server._sockets) > 0
        for s in http_server._sockets:
            actual_port = http_server._sockets[s].getsockname()[1]
            break

    info = {
        "port":actual_port,
    }
    queue.put_nowait(info)
    tornado.ioloop.IOLoop.instance().start()

class BaseTestCase(unittest.TestCase):                                                                                        
    def setUp(self):                                                                                                             
        self.application = Application()                                                                                                                 
                                                                                                                                  
        self.queue = multiprocessing.Queue()                                                                                                                                                                                                        
        self.server_process = create_process(0, self.queue, start_application_server, self.application)

        options = Options()
        options.add_argument("--headless")

        self.driver = webdriver.Firefox(firefox_options=options)                                                            
                                                                                                                               
    def tearDown(self):                                                                                                          
        self.driver.quit()                                                                                                       
        self.server_process.terminate()

    def wait_for_element(self, element_id, timeout=10):
        return WebDriverWait(self.driver, timeout).until( EC.presence_of_element_located((By.ID, element_id)))
