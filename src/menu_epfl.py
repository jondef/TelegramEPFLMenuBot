import datetime
import json
import urllib.parse
from datetime import timedelta
from functools import wraps
from io import BytesIO

# pip install requests
import requests
import telegram.parsemode
# pip install pillow
from PIL import Image
# pip install selenium
from selenium import webdriver
from selenium.common.exceptions import TimeoutException
from selenium.webdriver.chrome.options import Options
# pip install python-telegram-bot --upgrade
from telegram.ext import Updater, CommandHandler, MessageHandler, Filters
# pip install timeloop
from timeloop import Timeloop


# selenium requires chromedriver:
# $ yay -S chromium // chromium browser comes included with chromedriver


def start_driver():
	chrome_options = Options()
	chrome_options.add_argument("--headless")
	chrome_options.add_argument("--window-size=1920x1080")
	driver = webdriver.Chrome(options=chrome_options, executable_path="chromedriver")
	driver.set_page_load_timeout(30)
	print("Driver started!")
	return driver


def get_bot_token():
	"""
	Tries to get the token from bot_access_token.txt
	If the file doesn't exist, the program creates the file and
	then exits
	:return: bot token
	"""
	bot_access_token_file = "bot_access_token.txt"
	try:
		with open(bot_access_token_file, 'r') as token_file:
			access_token = token_file.readline().rstrip()
	except IOError:
		print(f"{bot_access_token_file} not found. Creating file...\nPlease enter your token in the file")
		token_file = open(bot_access_token_file, "w")
		token_file.close()
		exit(1)
	else:
		print(f"Using bot token: {access_token}")
		return access_token


def run_once(func):
	@wraps(func)
	def wrapper(*args, **kwargs):
		if not wrapper.has_run:
			wrapper.has_run = True
			return func(*args, **kwargs)

	wrapper.has_run = False
	return wrapper


@run_once
def init_bot():
	global UPDATER, BOT_TOKEN

	BOT_TOKEN = get_bot_token()
	UPDATER = Updater(token=BOT_TOKEN, use_context=True)


#################################################
#												#
# !			Helper functions					#
#												#
#################################################


def get_menu_website():
	# go to the main website
	DRIVER.get("https://www.epfl.ch/campus/restaurants-shops-hotels/fr/restauration/")

	# print the available categories to the user and ask which one to select
	restaurant_categories = ["Restaurants", "Self-Service", "Cafétérias", "Food-trucks"]
	selected_resto = restaurant_categories[2]
	# go to the selected category
	link = DRIVER.find_element_by_xpath(f"//a[contains(@class, 'h3') and contains(text(), '{selected_resto}')]")
	driver_click(DRIVER, link)

	# get the available services
	resto_element = DRIVER.find_elements_by_class_name("card-body")
	available_resto = []
	for x, y in enumerate(resto_element):
		available_resto.append(y.text)
		print(f"{x + 1} {y.text}")

	chosen_resto = available_resto[3]

	# go into the selected restaurant
	link = DRIVER.find_element_by_xpath(f"//a[contains(text(), '{chosen_resto}')]")
	DRIVER.execute_script("arguments[0].click();", link)

	frame = DRIVER.find_element_by_id("epfl-restauration")
	restaurant_link = frame.get_attribute("src")

	parsed = urllib.parse.urlparse(restaurant_link)
	restaurant_id = urllib.parse.parse_qs(parsed.query)["resto_id"][0]

	print(restaurant_id)


# link = driver.find_element_by_xpath("/html/body/div[2]/div[1]/div[2]/div[1]/main/article/div/div[2]/div/div/div[1]/div/div/a")
# link.click()

# link = driver.find_element_by_link_text('Sauce Labs')
# link.click()

# switch to iframe driver.switch_to.frame(driver.find_element_by_tag_name('iframe'))

def driver_click(driver, element):
	driver.execute_script("arguments[0].click();", element)


def capture_menu_pic(aResto_id: int):
	# does some web scraping to collect the image of the menu
	# returns a bytesIO type of the image, which can directly be used
	# returns None if picture not found/available
	# to send the image with the telegram API
	try:
		DRIVER.get(f"https://menus.epfl.ch/cgi-bin/getMenus?resto_id={aResto_id}&lang=fr")
	except TimeoutException:
		return None

	total_height = DRIVER.execute_script("return document.body.parentNode.scrollHeight")
	total_width = 1000  # can tweak the value of this

	DRIVER.set_window_size(total_width, total_height)

	# find the element menulist and get its size and location
	element = DRIVER.find_element_by_id("menulist")
	location = element.location
	size = element.size

	left = location['x']
	top = location['y']
	right = location['x'] + size['width']
	bottom = location['y'] + size['height']

	# get the image of the whole page and open it in memory
	png = DRIVER.get_screenshot_as_png()
	image = Image.open(BytesIO(png))

	# crop the image to fit the ul element
	im = image.crop((left, top, right, bottom))

	# convert image to bytesIO to avoid saving it to the disk
	bytesio = BytesIO()
	bytesio.name = 'menu.png'
	im.save(bytesio, format='png')
	bytesio.seek(0)

	# with open("screenshot.png", 'rb') as file:
	#    context.bot.send_photo(chat_id=update.effective_chat.id, photo=file)

	# driver.get_screenshot_as_file("capture.png")
	# element.screenshot("path.png")
	# driver.quit()
	return bytesio


#################################################


def get_admin_ids(update, context):
	return [admin.user.id for admin in context.bot.get_chat_administrators(update.effective_chat.id)]


def user_is_admin(update, context):
	if update.effective_user.id in get_admin_ids(update, context):
		return True
	else:
		return False


#################################################


# sends the pictures of the menu with the appropriate caption
def send_menu_pics(chat_id, bot):
	for restaurant_data in JSON_DATA["chats"][str(chat_id)]["restaurants"]:
		# if a picture of the menu was found
		if restaurant_data["id"] != "None":
			pic = capture_menu_pic(restaurant_data["id"])
			# if getting picture timed out
			if pic is None:
				bot.send_message(chat_id=chat_id, text=f"TimeoutException getting id {restaurant_data['id']}")
				continue

			bot.send_photo(chat_id, pic, caption=f"{restaurant_data['name']}'s menu", disable_notification=False,
			               reply_to_message_id=None, reply_markup=None, timeout=20, parse_mode=None)


def send_menu_text(update, context):
	# todo: wtf does that function do?
	for restaurant_data in JSON_DATA[str(update.effective_chat.id)]["Restaurant"]:
		# if a picture of the menu was found
		if restaurant_data["id"] != "None":
			context.bot.send_message(chat_id=update.effective_chat.id, text="")


def send_menu_link(update, context):
	pass  # todo: implement it


#################################################


def dump_to_config_file(data: dict):
	"""
	Call this function when you want to dump the modified
	json data to the config file.
	:param data: modified data
	:return: None
	"""
	try:
		with open("config.json", 'w') as file:
			json.dump(data, file, indent=4, sort_keys=True, ensure_ascii=False)
	except IOError as exc:
		print("Error writing to config file. Exiting.")
		exit(exc)


##########################################


# noinspection PyUnboundLocalVariable
def get_json_data():
	"""
	Tries to get the json data from the config file.
	If the file doesn't exist, it creates a new one with
	the default data and returns the data.'
	:return: json data as a dict
	"""
	try:
		with open("config.json", 'r') as file:
			print("Config.json found!")
			data = dict(json.load(file))
	except IOError:
		print("Config.json not found. Creating...")
		file = open("config.json", "w")
		file.close()
		data = {"chats": {}}
		dump_to_config_file(data)
	finally:
		return data


###########################################


def send_action(action):
	# send action while processing function
	def decorator(func):
		@wraps(func)
		def command_func(update, context, *args, **kwargs):
			context.bot.send_chat_action(chat_id=update.effective_message.chat_id, action=action)
			return func(update, context, *args, **kwargs)

		return command_func

	return decorator


def admin_only(input_func):
	@wraps(input_func)
	def wrapped(update, context, *args, **kwargs):
		# if update or context are not passed, just call the function
		if update is None or context is None:
			return input_func(update, context, *args, **kwargs)
		# if user is in a private chat with the bot, allow every function
		elif update.effective_chat.type == "private":
			return input_func(update, context, *args, **kwargs)
		elif user_is_admin(update, context):
			return input_func(update, context, *args, **kwargs)
		else:
			# todo: reply to message that got denied
			print(f"Unauthorized access denied for {update.effective_user.id}.")
			context.bot.send_message(chat_id=update.effective_chat.id, text="only admins can run this command")
			return

	return wrapped


#################################################
#												#
# !			Bot functions						#
#												#
#################################################


def my_add_handler(handler):
	# This code will run only once per decorated function.
	try:
		# try to add the handler
		UPDATER.dispatcher.add_handler(handler)
	except NameError:
		# if UPDATER has not been initialized yet
		init_bot()
	finally:
		# try to add the handler again
		UPDATER.dispatcher.add_handler(handler)

	def decorator(input_func):
		@wraps(input_func)
		def wrapped(update, context, *args, **kwargs):
			return input_func(update, context, *args, **kwargs)

		return wrapped

	return decorator


@my_add_handler(CommandHandler("help", lambda *args, **kwargs: help_handler(*args, **kwargs)))
def help_handler(update, context):
	context.bot.send_message(chat_id=update.effective_chat.id, text=
	"`/help` - Print this message\n"
	"`/menu` - Get the menus with the images and poll\n"
	"\n"
	"--- for group admins only ---\n"
	"`/start` - Creates config for the chat id\n"
	"`/reset` - Deletes all the config for the chat id\n"
	"`/addrestaurant` - Adds a restaurant (arg1 = name, arg2 = id)\n"
	"`/removerestaurant` - Removes a restaurant (arg1 = name)\n"
	"`/listrestaurants` - Lists added restaurants\n"
	"`/setmenulimit` - Sets how many times `/menu` can be called per day (arg1 = int)\n"
	"`/setmenudisplay` - Sets how the menu should be displayed (arg1 = 'image' | 'text' | 'link')\n"
	"`/setautosendmenu` - Send menu automatically at specified time (arg1 = 'true' | 'false')\n"
	"`/setautosendmenutime` - Sets the time at which to send the menu (arg1 = hour, arg2 = min)",
	                         parse_mode=telegram.ParseMode.MARKDOWN)


######################################


@send_action(telegram.ChatAction.TYPING)
@my_add_handler(CommandHandler("menu", lambda *args, **kwargs: menu_handler(*args, **kwargs)))
def menu_handler(update, context):
	menu(update.effective_chat.id, context.bot)


def menu(chat_id, bot):
	# if the limit of menu sent has been exceeded, cancel
	if int(JSON_DATA["chats"][str(chat_id)]["menuSentToday"]) >= int(
			JSON_DATA["chats"][str(chat_id)]["menuSendLimitPerDay"]):
		bot.send_message(chat_id=chat_id, text="Daily menu limit reached!")
		return

	# if there is a limit set per day, increment the count by one
	if int(JSON_DATA["chats"][str(chat_id)]["menuSendLimitPerDay"]) > 0:
		JSON_DATA["chats"][str(chat_id)]["menuSentToday"] = str(
			int(JSON_DATA["chats"][str(chat_id)]["menuSentToday"]) + 1)
		dump_to_config_file(JSON_DATA)

	pollQuestion = "Where do you want to eat?"
	pollOptions = [f"{Restaurant['name']} 🖼" if Restaurant["id"] != "None" else Restaurant["name"] for Restaurant in
	               JSON_DATA["chats"][str(chat_id)]["restaurants"]]

	bot.send_message(chat_id=chat_id, text="Alright, Alright, Alright!")

	# send menu
	if JSON_DATA["chats"][str(chat_id)]["menuDisplayType"] == "image":
		send_menu_pics(chat_id, bot)
	elif JSON_DATA["chats"][str(chat_id)]["menuDisplayType"] == "text":
		send_menu_text(chat_id, bot)
	elif JSON_DATA["chats"][str(chat_id)]["menuDisplayType"] == "link":
		send_menu_link(chat_id, bot)

	# send poll with multiple answers
	# the api doesn't support polls with multiple answers
	link = f"https://api.telegram.org/bot{BOT_TOKEN}/sendPoll?chat_id={chat_id}&question={pollQuestion.replace(' ', '+')}&options={json.dumps(pollOptions)}&allows_multiple_answers=true&is_anonymous=false"
	requests.get(link)


##############################

@admin_only
@my_add_handler(CommandHandler("start", lambda *args, **kwargs: start_handler(*args, **kwargs)))
def start_handler(update, context):
	# configure the start command
	# if the current chat id is not in data
	if str(update.effective_chat.id) not in JSON_DATA["chats"]:
		JSON_DATA["chats"][str(update.effective_chat.id)] = {
			# todo: save initial variables here
			"restaurants": [],
			"autoSendMenu": "false",
			"autoSendMenuTimeOfDay": "1130",
			"menuDisplayType": "image",
			"menuSentToday": "0",
			"menuSendLimitPerDay": "10"
		}
		dump_to_config_file(JSON_DATA)
		context.bot.send_message(chat_id=update.effective_chat.id, text="Chat added")

	context.bot.send_message(
		chat_id=update.effective_chat.id, text="Type `/help` to get started!", parse_mode=telegram.ParseMode.MARKDOWN)


#############################

@admin_only
@my_add_handler(CommandHandler("reset", lambda *args, **kwargs: reset_handler(*args, **kwargs)))
def reset_handler(update, context):
	# todo: finish this # make this function server owner only
	context.bot.send_message(chat_id=update.effective_chat.id, text="not implemented")


#############################

@my_add_handler(CommandHandler("update", lambda *args, **kwargs: update_handler(*args, **kwargs)))
def update_handler(update, context):
	# todo: this function is supposed to update the bot script
	pass


#############################

@admin_only
@my_add_handler(CommandHandler("addrestaurant", lambda *args, **kwargs: add_restaurant(*args, **kwargs)))
def add_restaurant(update, context):
	# todo: add ability to add restaurant with spaces
	if len(context.args) == 2:
		restaurant_name = context.args[0]
		restaurant_id = context.args[1]

		JSON_DATA["chats"][str(update.effective_chat.id)]["restaurants"].append({
			"name": restaurant_name,
			"id": restaurant_id
		})
		dump_to_config_file(JSON_DATA)

		context.bot.send_message(chat_id=update.effective_chat.id,
		                         text=f"Successfully added restaurant '{restaurant_name}' with id {restaurant_id} !")


#############################

@admin_only
@my_add_handler(CommandHandler("removerestaurant", lambda *args, **kwargs: remove_restaurant(*args, **kwargs)))
def remove_restaurant(update, context):
	restaurant_to_delete = ' '.join(context.args).lower()

	for i in range(len(JSON_DATA["chats"][str(update.effective_chat.id)]["restaurants"])):
		if JSON_DATA["chats"][str(update.effective_chat.id)]["restaurants"][i]['name'].lower() == restaurant_to_delete:
			del JSON_DATA["chats"][str(update.effective_chat.id)]["restaurants"][i]
			dump_to_config_file(JSON_DATA)
			context.bot.send_message(chat_id=update.effective_chat.id,
			                         text=f"Successfully removed restaurant '{restaurant_to_delete}' !")
			return

	context.bot.send_message(chat_id=update.effective_chat.id, text="Operation failed")


#############################

@admin_only
@my_add_handler(CommandHandler("listrestaurants", lambda *args, **kwargs: list_restaurants(*args, **kwargs)))
def list_restaurants(update, context):
	for restaurant in JSON_DATA["chats"][str(update.effective_chat.id)]["restaurants"]:
		context.bot.send_message(chat_id=update.effective_chat.id,
		                         text=f"name: {restaurant['name']} | id: {restaurant['id']}")


##############################

@admin_only
@my_add_handler(CommandHandler("setmenulimit", lambda *args, **kwargs: set_menu_limit(*args, **kwargs)))
def set_menu_limit(update, context):
	# todo: allow negative numbers?
	limit = 0
	try:
		limit = int(context.args[0])
	except ValueError:
		context.bot.send_message(chat_id=update.effective_chat.id, text="Invalid argument")
		return

	JSON_DATA["chats"][str(update.effective_chat.id)]["menuSendLimitPerDay"] = str(limit)
	dump_to_config_file(JSON_DATA)
	context.bot.send_message(chat_id=update.effective_chat.id, text="Updated!")


##############################

@admin_only
@my_add_handler(CommandHandler("setmenudisplay", lambda *args, **kwargs: set_menu_display(*args, **kwargs)))
def set_menu_display(update, context):
	arg = context.args[0]
	if arg == "image" or arg == "text" or arg == "link":
		JSON_DATA["chats"][str(update.effective_chat.id)]["menuDisplayType"] = context.args[0]
		dump_to_config_file(JSON_DATA)
		context.bot.send_message(chat_id=update.effective_chat.id, text="Updated!")
	else:
		context.bot.send_message(chat_id=update.effective_chat.id, text="Invalid argument")


##############################

@admin_only
@my_add_handler(CommandHandler("setautosendmenu", lambda *args, **kwargs: set_auto_send_menu(*args, **kwargs)))
def set_auto_send_menu(update, context):
	boolean = context.args[0].lower()
	if boolean == "true" or boolean == "false":
		JSON_DATA["chats"][str(update.effective_chat.id)]["autoSendMenu"] = boolean
		dump_to_config_file(JSON_DATA)
		context.bot.send_message(chat_id=update.effective_chat.id, text="Updated!")
	else:
		context.bot.send_message(chat_id=update.effective_chat.id, text="Invalid argument")


##############################


@admin_only
@my_add_handler(CommandHandler("setautosendmenutime", lambda *args, **kwargs: set_auto_send_menu_time(*args, **kwargs)))
def set_auto_send_menu_time(update, context):
	if len(context.args) != 2:
		context.bot.send_message(chat_id=update.effective_chat.id, text="Invalid argument")
		return

	try:
		hour = int(context.args[0])
		minute = int(context.args[1])
	except ValueError:
		context.bot.send_message(chat_id=update.effective_chat.id, text="Invalid argument")
		return

	if hour < 0 or hour > 23 or minute < 0 or minute > 59:
		context.bot.send_message(chat_id=update.effective_chat.id, text="Invalid argument")
		return

	hour = str(f"0{hour}") if hour < 10 else str(hour)
	minute = str(f"0{minute}") if minute < 10 else str(minute)

	JSON_DATA["chats"][str(update.effective_chat.id)]["autoSendMenuTimeOfDay"] = hour + minute
	dump_to_config_file(JSON_DATA)
	context.bot.send_message(chat_id=update.effective_chat.id, text=f"Auto send set to {hour}:{minute}!")


##############################

# this runs when the bots receives undefined commands
@my_add_handler(MessageHandler(Filters.text, lambda *args, **kwargs: echo(*args, **kwargs)))
def echo(update, context):
	context.bot.send_message(chat_id=update.effective_chat.id, text="Invalid command")


##############################

tl = Timeloop()


@tl.job(interval=timedelta(seconds=55))
def reset_sent_menu():
	# if it's midnight, iterate over every chat and reset the menuSentToday
	if datetime.datetime.now().hour == 0 and datetime.datetime.now().minute == 0:
		for chat in JSON_DATA["chats"]:
			# reset the menuSentToday variable
			JSON_DATA["chats"][chat]["menuSentToday"] = "0"

		dump_to_config_file(JSON_DATA)


@tl.job(interval=timedelta(seconds=55))
def auto_send_menu():
	# iterate over every chat
	for chat in JSON_DATA["chats"]:
		# we don't want to send the menu on weekends
		if datetime.datetime.now().weekday() == 5 or datetime.datetime.now().weekday() == 6:
			continue

		# if autoSendMenu == false, skip this chat
		if JSON_DATA["chats"][chat]["autoSendMenu"] == "false":
			continue

		# if hours don't match, continue
		if datetime.datetime.now().hour != int(JSON_DATA["chats"][chat]["autoSendMenuTimeOfDay"][:2]):
			continue

		# then check if the minutes matches
		if datetime.datetime.now().minute != int(JSON_DATA["chats"][chat]["autoSendMenuTimeOfDay"][-2:]):
			continue

		# send the menu
		bot = telegram.Bot(BOT_TOKEN)
		menu(chat, bot)


def main():
	global JSON_DATA, DRIVER

	init_bot()

	JSON_DATA = get_json_data()
	DRIVER = start_driver()

	UPDATER.start_polling()


# tl.start(block=True)


if __name__ == '__main__':
	main()
