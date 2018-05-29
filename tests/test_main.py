from .test_base import BaseTestCase

class MainHandlerTest(BaseTestCase):
    def testFormSubmit(self):                                                                                                    
        data = self.queue.get()                                                                                                  
        url = "http://localhost:%s" % (data['port'])
        self.driver.get(url)                                                                                       
        self.assertEqual("Vaindraft", self.driver.title)

        submit = self.wait_for_element("submit")
        submit.click()

        element = self.wait_for_element("startDraft")
        self.assertIsNotNone(element)