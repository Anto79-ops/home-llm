import argparse
import json
import csv
import random
from dataclasses import dataclass
from datasets import load_dataset, concatenate_datasets
from difflib import SequenceMatcher
from typing import Final, Any
from tqdm import tqdm
import webcolors

# #### STATES ####
STATE_ON: Final = "on"
STATE_OFF: Final = "off"
STATE_UNKNOWN: Final = "unknown"
STATE_OPEN: Final = "open"
STATE_OPENING: Final = "opening"
STATE_CLOSED: Final = "closed"
STATE_CLOSING: Final = "closing"
STATE_BUFFERING: Final = "buffering"
STATE_PLAYING: Final = "playing"
STATE_PAUSED: Final = "paused"
STATE_IDLE: Final = "idle"
STATE_STANDBY: Final = "standby"
STATE_LOCKED: Final = "locked"
STATE_UNLOCKED: Final = "unlocked"
STATE_LOCKING: Final = "locking"
STATE_UNLOCKING: Final = "unlocking"
STATE_JAMMED: Final = "jammed"
STATE_UNAVAILABLE: Final = "unavailable"
STATE_OK: Final = "ok"
STATE_PROBLEM: Final = "problem"

def closest_color(requested_color):
    min_colors = {}
    for key, name in webcolors.CSS3_HEX_TO_NAMES.items():
        r_c, g_c, b_c = webcolors.hex_to_rgb(key)
        rd = (r_c - requested_color[0]) ** 2
        gd = (g_c - requested_color[1]) ** 2
        bd = (b_c - requested_color[2]) ** 2
        min_colors[(rd + gd + bd)] = name
    return min_colors[min(min_colors.keys())]

@dataclass
class DeviceType:
    name: str
    possible_states: list[(str, float)]
    services: dict[str, list]

    def get_all_services(self, extra_exposed_attributes):
        result = []
        for service in self.services.keys():
            args = set(extra_exposed_attributes).intersection(self.services[service])
            result.append(f"{self.name}.{service}({','.join(args)})")
        return result

    def get_random_state(self, extra_exposed_attributes=[]):
        states = [ x[0] for x in self.possible_states ]
        weights = [ x[1] for x in self.possible_states ]
        return random.choices(states, weights=weights, k=1)[0]
    
class LightDeviceType(DeviceType):
    def __init__(self):
        super().__init__("light",
            possible_states=[
                (STATE_ON, 0.5),
                (STATE_OFF, 0.5)
            ],
            services={
                "turn_on": [ "rgb_color", "brightness" ],
                "turn_off": [],
                "toggle": []
            },
        )

    def get_random_state(self, extra_exposed_attributes=[]):
        state = super().get_random_state(extra_exposed_attributes=extra_exposed_attributes)

        if random.random() < 0.5 and "rgb_color" in extra_exposed_attributes:
            random_rgb = (random.randint(0, 255), random.randint(0, 255), random.randint(0, 255))
            state = state + ";" + closest_color(random_rgb) + " " + str(random_rgb)

        if random.random() < 0.7 and "brightness" in extra_exposed_attributes:
            state = state + ";" + str(random.randint(0, 100)) + "%"

        return state
    
class ClimateDeviceType(DeviceType):
    def __init__(self):
        super().__init__("climate", [], {
            "turn_on": [],
            "turn_off": [],
            "toggle": [],
            "set_temperature": ["temperature"],
            "set_humidity": ["humidity"],
            "set_fan_mode": ["fan_mode"],
            "set_hvac_mode": ["hvac_mode"],
            "set_preset_mode": ["preset_mode"]
        })

    def get_random_state(self, extra_exposed_attributes=[]):
        """state;fan_mode;temperature;humidity"""
        state = random.choice(["heat", "cool", "heat_cool", "off", "auto", "fan_only"])

        if "fan_mode" in extra_exposed_attributes:
            state = state  + ";" + random.choice(["On Low", "On High", "Auto Low", "Auto High", "Off"])
        if "temperature" in extra_exposed_attributes:
            if random.random() > 0.5:
                state = state + ";" + str(random.randint(60, 80)) + "F"
            else:
                state = state + ";" + str(random.randint(15, 25)) + "C"
        if "humidity" in extra_exposed_attributes:
            state = state + ";" + str(random.randint(10, 90)) + "%"

        if "preset_mode" in extra_exposed_attributes:
            # if it is not "on a preset" then don't add the mode
            random_mode = random.choice(["home", "eco", "away", "auto", None, None, None])
            if random_mode:
                state = state + ";" + random_mode

        return state
    
with open("piles/pile_of_media_names.csv") as f:
    pile_of_media_names = [ x.strip() for x in f.readlines() ]

class MediaPlayerDeviceType(DeviceType):
    def __init__(self):
        super().__init__("media_player", [
            (STATE_ON, 0.15),
            (STATE_OFF, 0.54),
            (STATE_IDLE, 0.1),
            (STATE_PLAYING, 0.1),
            (STATE_PAUSED, 0.05),
            (STATE_STANDBY, 0.05),
            (STATE_BUFFERING, 0.01),
        ], {
            "turn_on": [],
            "turn_off": [],
            "toggle": [],
            "volume_up": [],
            "volume_down": [],
            "volume_mute": [],
            "media_play_pause": [],
            "media_play": [],
            "media_pause": [],
            "media_stop": [],
            "media_next_track": [],
            "media_previous_track": []
        })
        

    def get_random_state(self, extra_exposed_attributes=[]):
        state = super().get_random_state(extra_exposed_attributes=extra_exposed_attributes)

        if "media_title" in extra_exposed_attributes and state in [STATE_PLAYING, STATE_PAUSED, STATE_BUFFERING, STATE_ON]:
            state = state + ";" + random.choice(pile_of_media_names)

        if "volume_level" in extra_exposed_attributes and state != STATE_OFF:
            state = state + ";vol=" + str(round(random.random(), 2))
        return state

SUPPORTED_DEVICES = {
    "light": LightDeviceType(),
    "switch": DeviceType(
        name="switch",
        possible_states=[
            (STATE_ON, 0.5),
            (STATE_OFF, 0.5)
        ],
        services={
            "turn_on": [],
            "turn_off": [],
            "toggle": []
        },
    ),
    "fan": DeviceType(
        name="fan",
        possible_states=[
            (STATE_ON, 0.5),
            (STATE_OFF, 0.5)
        ],
        services={
            "turn_on": [],
            "turn_off": [],
            "toggle": [],
            "increase_speed": [],
            "decrease_speed": [],
        },
    ),
    "garage_door": DeviceType(
        name="garage_door",
        possible_states=[
            (STATE_OPEN, 0.49),
            (STATE_CLOSED, 0.49),
            (STATE_OPENING, 0.01),
            (STATE_CLOSING, 0.01)
        ],
        services={
            "open_cover": [],
            "close_cover": [],
            "stop_cover": [],
            "toggle": [],
        },
    ),
    "blinds": DeviceType(
        name="blinds",
        possible_states=[
            (STATE_OPEN, 0.49),
            (STATE_CLOSED, 0.49),
            (STATE_OPENING, 0.01),
            (STATE_CLOSING, 0.01)
        ],
        services={
            "open_cover": [],
            "close_cover": [],
            "stop_cover": [],
            "toggle": [],
        },
    ),
    "lock": DeviceType(
        name="lock",
        possible_states=[
            (STATE_LOCKED, 0.5),
            (STATE_UNLOCKED, 0.5),
        ],
        services={
            "lock": [],
            "unlock": [],
        },
    ),
    "media_player": MediaPlayerDeviceType(),
    "climate": ClimateDeviceType()
}

stacks_of_device_names = { x: [] for x in SUPPORTED_DEVICES.keys() }
with open("piles/pile_of_device_names.csv") as f:
    reader = csv.DictReader(f)
    pile_of_device_names = list(reader)
    for device_dict in pile_of_device_names:
        try:
            device_type = device_dict["device_name"].split(".")[0]
            stacks_of_device_names[device_type].append(device_dict)
        except KeyError as ex:
            print(ex)

with open("piles/pile_of_templated_actions.csv") as f:
    reader = csv.DictReader(f)
    pile_of_templated_actions = list(reader)
    processed_pile_of_templated_actions = []
    for action in pile_of_templated_actions:
        for x in range(int(action["multiplier"])):
            processed_pile_of_templated_actions.append(action)

    pile_of_templated_actions = processed_pile_of_templated_actions

with open("piles/pile_of_device_actions.csv") as f:
    reader = csv.DictReader(f)
    pile_of_device_actions = list(reader)

with open("piles/pile_of_responses.csv") as f:
    reader = csv.DictReader(f)
    raw_pile_of_responses = list(reader)

    pile_of_responses = {}
    for raw in raw_pile_of_responses:
        if raw["device_type"] not in pile_of_responses:
            pile_of_responses[raw["device_type"]] = {}    
        pile_of_responses[raw["device_type"]][raw["service"]] = [ raw["response_1"], raw["response_2"], raw["response_3"] ]

with open("piles/pile_of_status_requests.csv") as f:
    reader = csv.DictReader(f)
    pile_of_status_requests = list(reader)

def format_device_line(*, device_name: str, friendly_name: str, state: str):
    return (f"{device_name} '{friendly_name}' = {state}")

# generate a random list of devices for the context
def random_device_list(max_devices: int, avoid_device_names: list[str]):
    num_devices = random.randint(2, max_devices)

    local_device_names = { k: v[:] for k,v in stacks_of_device_names.items() }

    avoid_climate = False
    for avoid_device in avoid_device_names:
        avoid_type = avoid_device.split(".")[0]

        filtered_possible_devices = []
        for possible_device in local_device_names[avoid_type]:
            similarity_ratio = SequenceMatcher(None, avoid_device, possible_device["device_name"].split(".")[1]).ratio()

            if similarity_ratio < 0.4:
                filtered_possible_devices.append(possible_device)
        local_device_names[avoid_type] = filtered_possible_devices

        if avoid_type == "climate":
            avoid_climate = True

    possible_choices = []
    for device_type in local_device_names.keys():
        possible_choices.extend(local_device_names[device_type])
    

    device_types = set()
    device_list = []
    device_lines = []
    # TODO: randomly pick attributes for this list
    extra_exposed_attributes = ["rgb_color", "brightness", "temperature", "humidity", "fan_mode", "media_title", "volume_level"]

    while len(device_list) < num_devices:
        choice = random.choice(possible_choices)
        if choice["device_name"] in device_list:
            continue

        try:
            device_name = choice["device_name"]
            device_type = device_name.split(".")[0]
            friendly_name = choice["description"]

            # don't add random thermostats. we need to be careful about how we handle multiple thermostats
            if avoid_climate and device_type == "climate":
                continue

            state = SUPPORTED_DEVICES[device_type].get_random_state(extra_exposed_attributes=extra_exposed_attributes)
            device_lines.append(format_device_line(
                device_name=device_name,
                friendly_name=friendly_name,
                state=state
            ))
            device_list.append(device_name)
            device_types.add(device_type)
        except Exception as ex:
            print(f"bad device name: {choice}")
            print(repr(ex))

    return device_lines, list(device_types), list(extra_exposed_attributes)

def generate_static_example(action: dict, max_devices: int = 32):
    question = action["english_phrase"]
    target_device = action["device_name"]
    device_type = target_device.split(".")[0]
    service_name = f"{device_type}.{action['service_name']}"
    friendly_name = target_device.split(".")[1].replace("_", " ")

    device_list, device_types, extra_exposed_attributes = random_device_list(
        max_devices=max_devices, avoid_device_names=[target_device])

    # insert our target device somewhere random in the list
    index = random.randint(0, len(device_list))
    state = SUPPORTED_DEVICES[device_type].get_random_state(extra_exposed_attributes=extra_exposed_attributes)

    device_list.insert(index, format_device_line(
        device_name=target_device,
        friendly_name=friendly_name,
        state=state
    ))

    # gather a list of all available services
    available_services = []
    for x in set(device_types + [device_type]):
        available_services.extend(SUPPORTED_DEVICES[x].get_all_services(extra_exposed_attributes))

    return {
        "states": device_list,
        "available_services": list(available_services),
        "question": question.lower(),
        "answers": [ random.choice(pile_of_responses[device_type][action["service_name"]]).lower() ],
        "service_calls": [ { "service": service_name, "target_device": target_device } ]
    }

def generate_templated_example(template: dict, max_devices: int = 32):
    template_device_types: list[str] = template["device_type"].split("|")
    service_names: list[str] = [ f"{x}.{y}" for x, y in zip(template_device_types, template["service"].split("|")) ]
    question_template: str = template["english_phrase"]
    answer_template: str = template["assistant_response"]

    # choose a random device for this template
    chosen_devices = []
    for device_type in template_device_types:
        device_dict = random.choice(stacks_of_device_names[device_type])
        device_dict["type"] = device_type
        chosen_devices.append(device_dict)

    device_list, device_types, extra_exposed_attributes = random_device_list(
        max_devices=max_devices, avoid_device_names=[d["device_name"] for d in chosen_devices])

    # insert our target device somewhere random in the list
    for device_dict in chosen_devices:
        index = random.randint(0, len(device_list))
        if "<brightness>" in question_template and "brightness" not in extra_exposed_attributes:
            extra_exposed_attributes.append("brightness")
        if "<color>" in question_template and "rgb_color" not in extra_exposed_attributes:
            extra_exposed_attributes.append("rgb_color")
        if ("<temp_f>" in question_template or "<temp_c>" in question_template) \
            and "temperature" not in extra_exposed_attributes:
            extra_exposed_attributes.append("temperature")
        if "<humidity>" in question_template and "humidity" not in extra_exposed_attributes:
            extra_exposed_attributes.append("humidity")

        state = SUPPORTED_DEVICES[device_dict["type"]].get_random_state(extra_exposed_attributes=extra_exposed_attributes)
        device_name = device_dict["device_name"]
        friendly_name = device_dict["description"]

        device_list.insert(index, format_device_line(
            device_name=device_name,
            friendly_name=friendly_name,
            state=state
        ))

    # gather a list of all available services with arguments
    available_services = []
    for x in set(device_types + template_device_types):
        available_services.extend(SUPPORTED_DEVICES[x].get_all_services(extra_exposed_attributes))

    # generate the question
    if len(template_device_types) == 1:
        question = question_template.replace("<device_name>", chosen_devices[0]["description"])
        answer = answer_template.replace("<device_name>", chosen_devices[0]["description"])
    else:
        question = question_template
        answer = answer_template
        for i in range(len(template_device_types)):
            question = question.replace(f"<device_name{(i + 1)}>", chosen_devices[i]["description"])
            answer = answer.replace(f"<device_name{(i + 1)}>", chosen_devices[i]["description"])

    # generate the list of service calls and answers
    service_calls = []
    for device_dict, service in zip(chosen_devices, service_names):
        service_calls.append({ "service": service, "target_device": device_dict["device_name"] })

    if any(["climate" in service for service in service_names ]):
        if "<temp_f>" in question:
            temp_f = random.randint(60, 80)
            question = question.replace("<temp_f>", str(temp_f))
            answer = answer.replace("<temp_f>", str(temp_f))
            service_calls = [ { **call, "temperature": temp_f} for call in service_calls ]

        if "<temp_c>" in question:
            temp_c = random.randint(15, 25)
            question = question.replace("<temp_c>", str(temp_c))
            answer = answer.replace("<temp_c>", str(temp_c))
            service_calls = [ { **call, "temperature": temp_c} for call in service_calls ]

        if "<humidity>" in question:
            humidity = random.randint(0, 20) * 5
            question = question.replace("<humidity>", str(humidity))
            answer = answer.replace("<humidity>", str(humidity))
            service_calls = [ { **call, "humidity": humidity} for call in service_calls ]

    if any(["light" in service for service in service_names ]):
        if "<brightness>" in question:
            brightness = random.randint(0, 100)
            question = question.replace("<brightness>", str(brightness))
            answer = answer.replace("<brightness>", str(brightness))
            service_calls = [ { **call, "brightness": round(brightness / 100, 2) } for call in service_calls ]

        if "<color>" in question:
            random_rgb = (random.randint(0, 255), random.randint(0, 255), random.randint(0, 255))
            random_rgb_name = closest_color(random_rgb)
            actual_random_rgb = webcolors.name_to_rgb(random_rgb_name)
            actual_random_rgb = (actual_random_rgb.red, actual_random_rgb.green, actual_random_rgb.blue)
            question = question.replace("<color>", str(random_rgb_name))
            answer = answer.replace("<color>", str(random_rgb_name))
            service_calls = [ { **call, "rgb_color": str(actual_random_rgb) } for call in service_calls ]
        

    return {
        "states": device_list,
        "available_services": list(available_services),
        "question": question.lower(),
        "answers": [ answer.lower() ],
        "service_calls": service_calls
    }

def generate_status_request(template: dict, max_devices: int = 32):
    device_type: str = template["device_type"]
    state_name: str = template["state"]
    question_template: str = template["english_phrase"]
    answer_template: str = template["assistant_response"]

    # choose a random device for this template
    chosen_device = random.choice(stacks_of_device_names[device_type])

    # build a random list of devices
    device_list, device_types, extra_exposed_attributes = random_device_list(max_devices=max_devices, avoid_device_names=[ chosen_device["device_name"] ])

    # insert our target device somewhere random in the list
    index = random.randint(0, len(device_list))

    # generate the question
    question = question_template.replace("<device_name>", chosen_device["description"])
    answer = answer_template.replace("<device_name>", chosen_device["description"])
    
    # insert other templated variables
    if device_type == "climate":
        temp_f = random.randint(60, 80)
        answer = answer.replace("<temp_f>", str(temp_f))
        state_name = state_name.replace("<temp_f>", str(temp_f))

        temp_c = random.randint(15, 25)
        answer = answer.replace("<temp_c>", str(temp_c))
        state_name = state_name.replace("<temp_c>", str(temp_f))

        humidity = random.randint(0, 20) * 5
        answer = answer.replace("<humidity>", str(humidity))
        state_name = state_name.replace("<humidity>", str(temp_f))

    if device_type == "light":
        brightness = random.randint(0, 100)
        answer = answer.replace("<brightness>", str(brightness))
        state_name = state_name.replace("<brightness>", str(brightness))

        random_rgb = (random.randint(0, 255), random.randint(0, 255), random.randint(0, 255))
        random_rgb_name = closest_color(random_rgb)
        actual_random_rgb = webcolors.name_to_rgb(random_rgb_name)
        actual_random_rgb = (actual_random_rgb.red, actual_random_rgb.green, actual_random_rgb.blue)
        state_name = state_name.replace("<color>", str(random_rgb_name) + " " + str(actual_random_rgb))
        answer = answer.replace("<color>", str(random_rgb_name))

    if device_type == "media_player":
        volume = random.randint(0, 100)
        random_media = random.choice(pile_of_media_names)

        answer = answer.replace("<volume>", str(volume) + "%")
        state_name = state_name.replace("<volume>", str(volume) + "%")

        answer = answer.replace("<media>", random_media)
        state_name = state_name.replace("<media>", random_media)

    device_list.insert(index, f"{chosen_device['device_name']} = {state_name}")

    # gather a list of all available services
    available_services = []
    for x in set(device_types + [device_type]):
        available_services.extend(SUPPORTED_DEVICES[x].get_all_services(extra_exposed_attributes))

    return {
        "states": device_list,
        "available_services": list(available_services),
        "question": question.lower(),
        "answers": [ answer.lower() ],
        "service_calls": []
    }

def format_example(example):
    sys_prompt = "You are 'Al', a helpful AI Assistant that controls the devices in a house. Complete the following task as instructed or answer the following question with the information provided only."
    services_block = "Services: " + ", ".join(sorted(example["available_services"]))
    states_block = "Devices:\n" + "\n".join(example["states"])
    question = example["question"]
    answers = " ".join(example["answers"])

    system_block = "\n".join([ "<|im_start|>system", sys_prompt, services_block, states_block ]) + "<|im_end|>"
    user_block = "\n".join([ "<|im_start|>user", question]) + "<|im_end|>"

    assistant_block = "<|im_start|>assistant\n" + answers
    if len(example["service_calls"]) > 0:
        json_calls = [ json.dumps(x) for x in example["service_calls"] ]
        code_block = "\n```homeassistant\n" + "\n".join(json_calls) + "\n```"
        assistant_block = assistant_block + code_block
    assistant_block = assistant_block + "<|im_end|>"
        
    example_lines = [system_block, user_block, assistant_block]
    result = "\n".join(example_lines)
    if "<device_name" in result:
        print("bad templating")

    # replace aliases with their actual values
    result = result.replace("blinds.", "cover.")
    result = result.replace("garage_door.", "cover.")
    return result


def generate_example_file(filename: str, seed: int, *, static_factor: int, template_factor: int, status_request_factor: int):
    random.seed(seed)

    print("Generating...")

    def run_factor_times(func, examples, data, factor):
        if factor >= 1:
            for i in range(factor):
                examples.append({ "text": format_example(func(data)) })
        else:
            if random.random() < factor:
                examples.append({ "text": format_example(func(data)) })
    
    generated_examples = []
    for action in tqdm(pile_of_device_actions):
        run_factor_times(generate_static_example, generated_examples, action, static_factor)

    for templated_action in tqdm(pile_of_templated_actions):
        run_factor_times(generate_templated_example, generated_examples, templated_action, template_factor)

    for status_request in tqdm(pile_of_status_requests):
        run_factor_times(generate_status_request, generated_examples, status_request, status_request_factor)

    print(f"Generated {len(generated_examples)} examples. Saving...")
    with open(f"{filename}.json", "w") as f:
        json.dump(generated_examples, f, indent=4)

    print("Done!")

def format_alpaca(example):
    question = example["instruction"]
    if "input" in example and example["input"]:
        question = question = "\n" + example["input"]

    answer = example["output"]

    device_list, device_types, extra_exposed_attributes = random_device_list(
        max_devices=32, avoid_device_names=[])

    available_services = []
    for x in device_types:
        available_services.extend(SUPPORTED_DEVICES[x].get_all_services(extra_exposed_attributes))

    text = format_example(example={
        "states": device_list,
        "available_services": list(available_services),
        "question": question,
        "answers": [ answer ],
        "service_calls": []
    })

    result = {
        "text": text
    }

    return result

def merge_with_dataset(dataset_name, seed, outupt_name, format_function, dataset_column_names):
    alpaca_dataset = load_dataset(dataset_name)["train"].train_test_split(test_size=0.1)
    home_assistant_dataset = load_dataset("json", data_files={  "train": "home_assistant_train.json", "test": "home_assistant_test.json" })

    random.seed(seed)

    alpaca_dataset = alpaca_dataset.map(format_function).remove_columns(dataset_column_names)

    combined_dataset_train = concatenate_datasets([home_assistant_dataset["train"], alpaca_dataset["train"]]).shuffle(seed=42)
    combined_dataset_test = concatenate_datasets([home_assistant_dataset["test"], alpaca_dataset["test"]]).shuffle(seed=42)

    combined_dataset_train.to_json(f"home_assistant_{outupt_name}_merged_train.json")
    combined_dataset_test.to_json(f"home_assistant_{outupt_name}_merged_test.json")


# TODO: add examples for ambiguous requests. asking a clarifying question
# TODO: make more randomized names for devices (random words or people's names)
# TODO: answer questions about more than one thing in the state list at once
# TODO: add examples for rooms/groups of devices. i.e. "turn off all the lights in the kitchen"
def main():
    parser = argparse.ArgumentParser(description="Generate the full dataset from the CSV piles")
    parser.add_argument("--sample", action="store_true", help="Set this flag to enable generation of the train dataset.")
    parser.add_argument("--test", action="store_true", help="Set this flag to enable generation of the train dataset..")
    parser.add_argument("--train", action="store_true", help="Set this flag to enable generation of the train dataset.")
    parser.add_argument("--merge", help="Set this flag to merge the generated datasets with the specified dataset.")
    train_size_group = parser.add_mutually_exclusive_group()
    train_size_group.add_argument('--small', action='store_const', const='small', dest='size')
    train_size_group.add_argument('--medium', action='store_const', const='medium', dest='size')
    train_size_group.add_argument('--large', action='store_const', const='large', dest='size')
    train_size_group.add_argument('--xl', action='store_const', const='xl', dest='size')

    args = parser.parse_args()

    if args.sample:
        generate_example_file("sample", 42, static_factor=1, template_factor=1, status_request_factor=1)
    if args.train:
        # TODO: add small, medium, large cli clags
        if args.size == "small":
            generate_example_file("home_assistant_train", 42, static_factor=1, template_factor=10, status_request_factor=8)
        elif args.size == "medium":
            generate_example_file("home_assistant_train", 42, static_factor=5, template_factor=15, status_request_factor=12)
        elif args.size == "large":
            generate_example_file("home_assistant_train", 42, static_factor=5, template_factor=20, status_request_factor=15)
        elif args.size == "xl":
            generate_example_file("home_assistant_train", 42, static_factor=7, template_factor=25, status_request_factor=18)
        else:
            raise Exception(f"Unrecognized dataset size: {args.size}")
    if args.test:
        generate_example_file("home_assistant_test", 12345, static_factor=0.25, template_factor=3, status_request_factor=2)

    if args.merge == "alpaca":
        merge_with_dataset("yahma/alpaca-cleaned", 42, "alpaca", format_alpaca, ["input", "output", "instruction"])
    elif args.merge == "wizardlm70k":
        merge_with_dataset("WizardLM/WizardLM_evol_instruct_70k", 42, "wizardlm70k", format_alpaca, ["output", "instruction"])

if __name__ == "__main__":
    main()