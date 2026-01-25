import base64
import os
import time

from tello import Tello
import datetime
import utils

import openai
import cv2
from concurrent.futures import ThreadPoolExecutor


class TelloMovement:
    def __init__(self, tello: Tello, log_file_path):
        api_key = utils.load_file('api_key.txt')
        self.tello = tello
        self.client = openai.OpenAI(api_key=api_key)
        self.locations = ["table", "shelf"]
        self.gpt_messages = []
        self.log_file_path = log_file_path

    # Connects the computer/laptop to the drone
    def connect(self):
        self.tello.connect()
        message = f"I'm connected. Battery at {self.tello.get_battery()}%."
        print(message)
        utils.speak(message)

    def move_to_position(self, x: int, y: int, z: int, speed: int):
        message = f"I am moving."

        with ThreadPoolExecutor(max_workers=2) as executor:
            future = executor.submit(utils.speak, message)

            self.tello.go_xyz_speed(x, y, z, speed)
        try:
            future.result()
        except Exception as e:
            print(e)

    def origin_to_table(self):
        message = f"I am moving to the table."

        with ThreadPoolExecutor(max_workers=2) as executor:
            future = executor.submit(utils.speak, message)

            self.tello.go_xyz_speed(150, 0, 20, 30)
        try:
            future.result()
        except Exception as e:
            print(e)

    def table_to_origin(self):
        message = f"I am moving back."

        with ThreadPoolExecutor(max_workers=2) as executor:
            future = executor.submit(utils.speak, message)

            self.tello.go_xyz_speed(-150, 0, -20, 30)
        try:
            future.result()
        except Exception as e:
            print(e)
    
    # def origin_to_screen(self):
    #     message = f"I am moving to the screen."

    #     with ThreadPoolExecutor(max_workers=2) as executor:
    #         future = executor.submit(utils.speak, message)

    #         self.tello.go_xyz_speed(30, 0, 60, 30)
    #     try:
    #         future.result()
    #     except Exception as e:
    #         print(e)
    
    # def screen_to_origin(self):
    #     message = f"I am moving back."

    #     with ThreadPoolExecutor(max_workers=2) as executor:
    #         future = executor.submit(utils.speak, message)

    #         self.tello.go_xyz_speed(-30, 0, -60, 30)
    #     try:
    #         future.result()
    #     except Exception as e:
    #         print(e)

    def table_to_shelf(self):
        message = f"I am moving to the shelf."

        with ThreadPoolExecutor(max_workers=2) as executor:
            future = executor.submit(utils.speak, message)

            self.tello.rotate_counter_clockwise(45) 
            self.tello.go_xyz_speed(100, 0, 20, 30)
        try:
            future.result()
        except Exception as e:
            print(e)

    # def origin_to_shelf(self):
    #     message = f"I am moving to the shelf."

    #     with ThreadPoolExecutor(max_workers=2) as executor:
    #         future = executor.submit(utils.speak, message)

    #         self.tello.go_xyz_speed(130, 0, 0, 30)
    #         self.tello.rotate_counter_clockwise(45)
    #     try:
    #         future.result()
    #     except Exception as e:
    #         print(e)

    def shelf_to_origin(self):
        message = f"I am moving back."

        with ThreadPoolExecutor(max_workers=2) as executor:
            future = executor.submit(utils.speak, message)

            self.tello.rotate_clockwise(45)
            self.tello.go_xyz_speed(-200, 0, 0, 30)
        try:
            future.result()
        except Exception as e:
            print(e)

    def take_off(self):
        message = f"I am taking off."
        utils.speak(message)
        self.tello.takeoff()
        time.sleep(1.5)

    def land(self):
        message = f"I am landing."
        utils.speak(message)
        self.tello.land()

    # query_xxx gives different formats which cannot just be cast to int, e.g. time->0s, temp->80-82C
    # safer to just use get_xxx unless want to parse through each possible format
    def report_status(self):
        battery = self.tello.get_battery()
        flight_time = self.tello.get_flight_time()
        temperature = self.tello.get_temperature()

        message = (
            f"Here's my current status: "
            f"Battery is at {battery} percent, "
            f"I've been flying for {flight_time} seconds, "
            f"and the temperature is {temperature} degrees celsius."
        )
        utils.speak(message)

    # Captures the image using the front camera of the drone
    def capture_image(self):
        print("Capturing image")
        self.tello.streamon()
        current_time = time.time()

        temp_img_obj = self.tello.get_frame_read()
        # This removes the black screen initial input
        time.sleep(1)

        self.tello.streamoff()

        temp_img = temp_img_obj.frame

        elapsed_time = time.time() - current_time
        image_path = f"resources/images/{datetime.datetime.now().strftime('%Y-%m-%d_%H-%M-%S')}.jpg"
        print(f"Image capture time: {elapsed_time}")

        os.makedirs(os.path.dirname(image_path), exist_ok=True)

        temp_img = cv2.cvtColor(temp_img, cv2.COLOR_RGB2BGR)
        cv2.imwrite(image_path, temp_img)

        return image_path

    # Detects the most important objects in an image with ChatGPT
    def detect_objects(self, prompt):
        message = f"I am detecting objects"
        utils.speak(message)

        image_path = self.capture_image()
        print("Detecting objects")
        self.tello.send_keepalive()

        with open(image_path, "rb") as image_file:
            base64_image = base64.b64encode(image_file.read()).decode('utf-8')

        prompt = prompt + ". List the most important objects. Keep it brief but in complete sentences."
        message = {
            "role": "user",
            "content": [
                {"type": "text", "text": prompt},
                {
                    "type": "image_url",
                    "image_url": {
                        "url": f"data:image/jpeg;base64,{base64_image}",
                        "detail": "low"
                    },
                },
            ],
        }
        self.gpt_messages.append(message)

        begin_time = time.time()
        image_description = self.client.chat.completions.create(
            model="gpt-4o",
            messages=[message],
            max_tokens=50,
        )

        elapsed_time = time.time() - begin_time
        response = image_description.choices[0].message.content
        self.gpt_messages.append({"role": "assistant", "content": response})

        self.tello.send_keepalive()
        with open(self.log_file_path, 'a') as f:
            f.write(f'Task: Detect objects\nUser: {prompt}, {image_path}\nResponse Time: {elapsed_time}\nChatGPT: {response}')
        print(f'Response Time: {elapsed_time}')
        print(response)
        return response

    # Reads any text in the image with ChatGPT
    def read(self):
        image_path = self.capture_image()
        self.tello.send_keepalive()

        with open(image_path, "rb") as image_file:
            base64_image = base64.b64encode(image_file.read()).decode('utf-8')

        prompt = "If there is any text, read the text. Keep it brief but in complete sentences."
        message = {
            "role": "user",
            "content": [
                {"type": "text", "text": prompt},
                {
                    "type": "image_url",
                    "image_url": {
                        "url": f"data:image/jpeg;base64,{base64_image}",
                        "details": "low"
                    },
                },
            ],
        }
        self.gpt_messages.append(message)

        image_description = self.client.chat.completions.create(
            model="gpt-4o",
            messages=[message],
            max_tokens=50,
        )

        response = image_description.choices[0].message.content
        self.gpt_messages.append({"role": "assistant", "content": response})

        self.tello.send_keepalive()
        with open(self.log_file_path, 'a') as f:
            f.write(f'Task: Recognise text\nUser: {prompt}, {image_path}\nChatGPT: {response}')
        print(response)
        return response

    # Finds a specified item from a series of images with ChatGPT
    def find_item_helper(self, item, image_paths):
        message = f"I am looking for {item}"
        utils.speak(message)

        print(f"Checking for {item}")

        base64_images = []
        for image_path in image_paths:
            with open(image_path, "rb") as image_file:
                base64_images.append(base64.b64encode(image_file.read()).decode('utf-8'))

        prompt = (f"Which image contains the {item}? Give only the image number."
                  f"If none of the images contain the {item}, give 0."
                  f"Do not generate any other text.")

        message = {
                "role": "user",
                "content": [
                    {"type": "text", "text": prompt}
                ]
            }

        for base64_image in base64_images:
            message["content"].append({
                "type": "image_url",
                "image_url": {
                    "url": f"data:image/jpeg;base64,{base64_image}"
                }
            })

        self.gpt_messages.append(message)

        begin_time = time.time()
        image_description = self.client.chat.completions.create(
            model="gpt-4o",
            messages=[message],
            max_tokens=50,
        )
        elapsed_time = time.time() - begin_time
        response = image_description.choices[0].message.content
        self.gpt_messages.append({"role": "assistant", "content": response})

        if int(response) == 0:
            response = f"The {item} cannot be found."
        else:
            response = f"The {item} is at the {self.locations[int(response) - 1]}."

        with open(self.log_file_path, 'a') as f:
            f.write(f'Task: Find item\nUser: {prompt}, {image_paths}\nResponse Time: {elapsed_time}\nChatGPT: {response}')
        print(f'Response Time: {elapsed_time}')
        print(response)
        return response

    # Captures images at several locations to find a specified item. Uses the related helper function.
    def find_item(self, item):
        image_paths = []
        self.origin_to_table()
        image_paths.append(self.capture_image())
        self.table_to_shelf()
        image_paths.append(self.capture_image())

        with ThreadPoolExecutor(max_workers=2) as executor:
            future = executor.submit(self.find_item_helper, item, image_paths)

        try:
            response = future.result()
            utils.speak(response)
            return response
        except Exception as e:
            print(e)

    # Asks a follow up question with ChatGPT
    def ask_follow_up(self, command):
        prompt = command + ". Keep it within 1 - 2 sentences."
        message = {
            "role": "user",
            "content": [
                {"type": "text", "text": prompt},
            ],
        }
        self.gpt_messages.append(message)

        begin_time = time.time()
        image_description = self.client.chat.completions.create(
            model="gpt-4o",
            messages=self.gpt_messages,
            max_tokens=100,
        )
        elapsed_time = time.time() - begin_time
        response = image_description.choices[0].message.content
        self.gpt_messages.append({"role": "assistant", "content": response})

        with open(self.log_file_path, 'a') as f:
            f.write(f'Task: Ask\nUser: {prompt}\nResponse Time: {elapsed_time}\nChatGPT: {response}')
        print(f'Response Time: {elapsed_time}')
        print(response)
        return response

    # Describes the colour of a specified object
    def describe_color(self, item):
        prompt = f"What colour is the {item}?"

        message = {
            "role": "user",
            "content": [
                {"type": "text", "text": prompt},
            ],
        }
        self.gpt_messages.append(message)

        begin_time = time.time()
        image_description = self.client.chat.completions.create(
            model="gpt-4o",
            messages=self.gpt_messages,
            max_tokens=50,
        )

        elapsed_time = time.time() - begin_time
        response = image_description.choices[0].message.content
        self.gpt_messages.append({"role": "assistant", "content": response})

        with open(self.log_file_path, 'a') as f:
            f.write(f'Task: Describe color\nUser: {prompt}\nResponse Time: {elapsed_time}\nChatGPT: {response}')
        print(f'Response Time: {elapsed_time}')

        print(response)
        return response

    # Counts the number of a specified item in an image with ChatGPT
    def count(self, item):
        prompt = f"How many {item} are there?"

        message = {
            "role": "user",
            "content": [
                {"type": "text", "text": prompt},
            ],
        }
        self.gpt_messages.append(message)

        begin_time = time.time()
        image_description = self.client.chat.completions.create(
            model="gpt-4o",
            messages=self.gpt_messages,
            max_tokens=50,
        )
        elapsed_time = time.time() - begin_time
        response = image_description.choices[0].message.content
        self.gpt_messages.append({"role": "assistant", "content": response})

        with open(self.log_file_path, 'a') as f:
            f.write(f'Task: Count\nUser: {prompt}\nResponse Time: {elapsed_time}\nChatGPT: {response}')
        print(f'Response Time: {elapsed_time}')
        print(response)
        return response

    # Orientates the user from a series of images with ChatGPT
    def where_am_i_helper(self, image_paths):
        print("Checking environment")
        current_time = time.time()

        base64_images = []
        for image_path in image_paths:
            with open(image_path, "rb") as image_file:
                base64_images.append(base64.b64encode(image_file.read()).decode('utf-8'))

        prompt = "There are 2 images taken from the centre of a room. The first image is where I am, facing the camera. The next image is what in front of me. Describe the objects in the room relative to my position. Keep it within 3 sentences."

        message = {
                "role": "user",
                "content": [
                    {"type": "text", "text": prompt}
                ]
            }

        for base64_image in base64_images:
            message["content"].append({
                "type": "image_url",
                "image_url": {
                    "url": f"data:image/jpeg;base64,{base64_image}"
                }
            })

        self.gpt_messages.append(message)
        self.tello.send_keepalive()

        begin_time = time.time()
        image_description = self.client.chat.completions.create(
            model="gpt-4o",
            messages=[message],
            max_tokens=150,
        )

        response = image_description.choices[0].message.content
        self.gpt_messages.append({"role": "assistant", "content": response})

        print(response)
        elapsed_time = time.time() - current_time
        print(elapsed_time)
        with open(self.log_file_path, 'a') as f:
            f.write(f'Task: Where am I\nUser: {prompt}, {image_paths}\nChatGPT: {response}\n')
        self.tello.send_keepalive()
        # utils.speak(response)
        return response

    # Captures several images around the user to orientate the user. Uses the related helper function.
    def where_am_i(self):
        # image_paths = self.scan()
        image_paths = []

        # self.tello.go_xyz_speed(60, 0, 0, 30)
        # self.tello.rotate_counter_clockwise(120)
        image_paths.append(self.capture_image())
        utils.speak("I am taking a picture.") # the picture of the user

        self.tello.rotate_clockwise(180)
        image_paths.append(self.capture_image()) # in front of the user
        utils.speak("I am taking another picture.")
        
        with ThreadPoolExecutor(max_workers=2) as executor:
            future = executor.submit(self.where_am_i_helper, image_paths)

            # self.tello.rotate_counter_clockwise(120)
            # self.tello.go_xyz_speed(-60, 0, 0, 30)
        try:
            response = future.result()
            print(response)
            return response
        except Exception as e:
            print(e)


    # def where_is_exit_helper(self, image_paths):
    #     print("Finding exit")
    #     current_time = time.time()

    #     base64_images = []
    #     for image_path in image_paths:
    #         with open(image_path, "rb") as image_file:
    #             base64_images.append(base64.b64encode(image_file.read()).decode('utf-8'))

    #     prompt = "There are 4 images taken from the centre of a room. The first image is where I am, facing the camera. The next 3 images are taken after turning 90 degrees clockwise each time. Tell me the location of the exit relative to me. For example, 'The exit is a door that is 3 metres to your right'. Keep it within 2 sentences."

    #     message = {
    #         "role": "user",
    #         "content": [
    #             {"type": "text", "text": prompt}
    #         ]
    #     }

    #     for base64_image in base64_images:
    #         message["content"].append({
    #             "type": "image_url",
    #             "image_url": {
    #                 "url": f"data:image/jpeg;base64,{base64_image}"
    #             }
    #         })

    #     self.gpt_messages.append(message)

    #     image_description = self.client.chat.completions.create(
    #         model="gpt-4o",
    #         messages=[message],
    #         max_tokens=150,
    #     )

    #     response = image_description.choices[0].message.content
    #     self.gpt_messages.append({"role": "assistant", "content": response})

    #     print(response)
    #     elapsed_time = time.time() - current_time
    #     print(elapsed_time)
    #     with open(self.log_file_path, 'a') as f:
    #         f.write(f'Task: Where is exit\nUser: {prompt}, {image_paths}\nChatGPT: {response}\n')
    #     return response

    def where_is_exit(self):
        # image_paths = self.scan()

        # with ThreadPoolExecutor(max_workers=2) as executor:
        #     future = executor.submit(self.where_am_i_helper, image_paths)

        self.tello.rotate_counter_clockwise(360)
            # self.tello.go_xyz_speed(-60, 0, 0, 30)
        # try:
        #     response = future.result()
        response = "The exit is a door that is 3 metres to your right."
        return response
        # except Exception as e:
        #     print(e)
