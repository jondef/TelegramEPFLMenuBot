import datetime
import json
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
from selenium.webdriver.chrome.options import Options
# pip install python-telegram-bot --upgrade
from telegram.ext import Updater, CommandHandler, MessageHandler, Filters
# pip install timeloop
from timeloop import Timeloop

# selenium requires chromedriver:
# $ yay -S chromium // chromium browser comes included with chromedriver


# configure the chrome driver
chrome_options = Options()
chrome_options.add_argument("--headless")
chrome_options.add_argument("--window-size=1920x1080")
chrome_driver = "chromedriver"
driver = webdriver.Chrome(options=chrome_options, executable_path=chrome_driver)

# configure the telegram bot
try:
	with open('bot_access_token.txt', 'r') as file:
		access_token = file.readline().rstrip()
		print(f"Using bot token: {access_token}")
except IOError:
	print("bot_access_token.txt not found. Creating file...Please enter your token in the file")
	file = open("bot_access_token.txt", "w")
	file.close()
	exit()

updater = Updater(token=access_token, use_context=True)
dispatcher = updater.dispatcher


#################################################
#												#
# !			Helper functions					#
#												#
#################################################


def captureMenuPic(aResto_id: int):
	# does some web scraping to collect the image of the menu
	# returns a bytesIO type of the image, which can directly be used
	# to send the image with the telegram API
	# todo: return None if picture not found/available

	driver.get(f"https://menus.epfl.ch/cgi-bin/getMenus?resto_id={aResto_id}&lang=fr")

	total_height = driver.execute_script("return document.body.parentNode.scrollHeight")
	total_width = 1000  # can tweak the value of this

	driver.set_window_size(total_width, total_height)

	# find the element menulist and get its size and location
	element = driver.find_element_by_id("menulist")
	location = element.location
	size = element.size

	left = location['x']
	top = location['y']
	right = location['x'] + size['width']
	bottom = location['y'] + size['height']

	# get the image of the whole page and open it in memory
	png = driver.get_screenshot_as_png()
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
	print(update)
	print(context)
	if update.effective_user.id in get_admin_ids(update, context):
		return True
	else:
		return False


#################################################


# sends the pictures of the menu with the appropriate caption
def sendMenuPics(chat_id, bot):
	for restaurant_data in data["chats"][str(chat_id)]["restaurants"]:
		# if a picture of the menu was found
		if restaurant_data["id"] != "None":
			bot.send_photo(chat_id, captureMenuPic(restaurant_data["id"]),
						   caption=f"{restaurant_data['name']}'s menu", disable_notification=False,
						   reply_to_message_id=None, reply_markup=None, timeout=20, parse_mode=None)


def sendMenuText(update, context):
	for restaurant_data in data[str(update.effective_chat.id)]["Restaurant"]:
		# if a picture of the menu was found
		if restaurant_data["id"] != "None":
			context.bot.send_message(chat_id=update.effective_chat.id, text="")


def sendMenulink(update, context):
	pass  # todo: implement it


#################################################

def dumpToConfigFile(data):
	try:
		with open("config.json", 'w') as file:
			json.dump(data, file, indent=4, sort_keys=True, ensure_ascii=False)
	except IOError:
		print("Error writing to config file. Exiting.")
		exit()


##########################################


# make sure the config.json file is present
try:
	with open("config.json", 'r') as file:
		print("Config.json found!")
except IOError:
	print("Config.json not found. Creating...")
	file = open("config.json", "w")
	data = {"chats": {}}
	dumpToConfigFile(data)

# load config to memory
with open('config.json') as file:
	data = dict(json.load(file))


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


def adminonly(input_func):
	def decorator(*args, **kwargs):
		# make sure that update and context are passed
		update = None
		context = None
		for arg in args:
			if type(arg) == telegram.update.Update:
				update = arg
			elif type(arg) == telegram.ext.callbackcontext.CallbackContext:
				context = arg

		# if update or context are not passed, just call the function
		if update is None or context is None:
			input_func(*args, **kwargs)

		# if user is in a private chat with the bot, allow every function
		elif update.effective_chat.type == "private":
			input_func(*args, **kwargs)

		elif user_is_admin(update, context):
			input_func(*args, **kwargs)
		else:
			context.bot.send_message(chat_id=update.effective_chat.id, text="only admins can run this command")

	return decorator


#################################################
#												#
# !			Bot functions						#
#												#
#################################################

def help(update, context):
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


help_handler = CommandHandler('help', help)
dispatcher.add_handler(help_handler)


######################################


@send_action(telegram.ChatAction.TYPING)
def menuHandler(update, context):
	menu(update.effective_chat.id, context.bot)


def menu(chat_id, bot):
	# if the limit of menu sent has been exeeded, cancel
	if int(data["chats"][str(chat_id)]["menuSentToday"]) >= int(
			data["chats"][str(chat_id)]["menuSendLimitPerDay"]):
		return

	# if there is a limit set per day, increment the count by one
	if int(data["chats"][str(chat_id)]["menuSendLimitPerDay"]) > 0:
		data["chats"][str(chat_id)]["menuSentToday"] = str(
			int(data["chats"][str(chat_id)]["menuSentToday"]) + 1)
		dumpToConfigFile(data)

	pollQuestion = "Where do you want to eat?"
	pollOptions = [f"{Restaurant['name']} 🖼" if Restaurant["id"] != "None" else Restaurant["name"] for Restaurant in
				   data["chats"][str(chat_id)]["restaurants"]]

	bot.send_message(chat_id=chat_id, text="Alright, Alright, Alright!")

	# send menu
	if data["chats"][str(chat_id)]["menuDisplayType"] == "image":
		sendMenuPics(chat_id, bot)
	elif data["chats"][str(chat_id)]["menuDisplayType"] == "text":
		sendMenuText(chat_id, bot)
	elif data["chats"][str(chat_id)]["menuDisplayType"] == "link":
		sendMenulink(chat_id, bot)

	# send poll with multiple answers
	# the api doesn't support polls with multiple answers
	link = f"https://api.telegram.org/bot{access_token}/sendPoll?chat_id={chat_id}&question={pollQuestion.replace(' ', '+')}&options={json.dumps(pollOptions)}&allows_multiple_answers=true"
	requests.get(link)


menu_handler = CommandHandler('menu', menuHandler)
dispatcher.add_handler(menu_handler)


##############################

@adminonly
def start(update, context):
	# configure the start command
	# if the current chat id is not in data
	if str(update.effective_chat.id) not in data["chats"]:
		data["chats"][str(update.effective_chat.id)] = {
			# todo: save initial variables here
			"restaurants": [],
			"autoSendMenu": "false",
			"autoSendMenuTimeOfDay": "1130",
			"menuDisplayType": "image",
			"menuSentToday": "0",
			"menuSendLimitPerDay": "10"
		}
		dumpToConfigFile(data)
		context.bot.send_message(chat_id=update.effective_chat.id, text="Chat added")

	context.bot.send_message(
		chat_id=update.effective_chat.id, text="Type `/help` to get started!", parse_mode=telegram.ParseMode.MARKDOWN)


start_handler = CommandHandler('start', start)
dispatcher.add_handler(start_handler)


#############################

@adminonly
def reset(update, context):
	# todo: finish this
	context.bot.send_message(chat_id=update.effective_chat.id, text="not implemented")


reset_handler = CommandHandler('reset', reset)
dispatcher.add_handler(reset_handler)


#############################

@adminonly
def add_restaurant(update, context):
	if len(context.args) == 2:
		restaurant_name = context.args[0]
		restaurant_id = context.args[1]

		data["chats"][str(update.effective_chat.id)]["restaurants"].append({
			"name": restaurant_name,
			"id": restaurant_id
		})
		dumpToConfigFile(data)

		context.bot.send_message(chat_id=update.effective_chat.id, text=
		f"Successfully added restaurant '{restaurant_name}' with id {restaurant_id} !")


add_restaurant_handler = CommandHandler('addrestaurant', add_restaurant)
dispatcher.add_handler(add_restaurant_handler)


#############################

@adminonly
def remove_restaurant(update, context):
	restaurant_to_delete = ' '.join(context.args).lower()

	for i in range(len(data["chats"][str(update.effective_chat.id)]["restaurants"])):
		if data["chats"][str(update.effective_chat.id)]["restaurants"][i]['name'].lower() == restaurant_to_delete:
			del data["chats"][str(update.effective_chat.id)]["restaurants"][i]
			dumpToConfigFile(data)
			context.bot.send_message(chat_id=update.effective_chat.id,
									 text=f"Successfully removed restaurant '{restaurant_to_delete}' !")
			return

	context.bot.send_message(chat_id=update.effective_chat.id, text="Operation failed")


remove_restaurant_handler = CommandHandler('removerestaurant', remove_restaurant)
dispatcher.add_handler(remove_restaurant_handler)


#############################

@adminonly
def listrestaurants(update, context):
	for restaurant in data["chats"][str(update.effective_chat.id)]["restaurants"]:
		context.bot.send_message(chat_id=update.effective_chat.id,
								 text=f"name: {restaurant['name']} | id: {restaurant['id']}")


listrestaurants_handler = CommandHandler('listrestaurants', listrestaurants)
dispatcher.add_handler(listrestaurants_handler)


##############################

@adminonly
def setmenulimit(update, context):
	# todo: allow negative numbers?
	limit = 0
	try:
		limit = int(context.args[0])
	except ValueError:
		context.bot.send_message(chat_id=update.effective_chat.id, text="Invalid argument")
		return

	data["chats"][str(update.effective_chat.id)]["menuSendLimitPerDay"] = str(limit)
	dumpToConfigFile(data)
	context.bot.send_message(chat_id=update.effective_chat.id, text="Updated!")


setmenulimit_handler = CommandHandler('setmenulimit', setmenulimit)
dispatcher.add_handler(setmenulimit_handler)


##############################

@adminonly
def setmenudisplay(update, context):
	arg = context.args[0]
	if arg == "image" or arg == "text" or arg == "link":
		data["chats"][str(update.effective_chat.id)]["menuDisplayType"] = context.args[0]
		dumpToConfigFile(data)
		context.bot.send_message(chat_id=update.effective_chat.id, text="Updated!")
	else:
		context.bot.send_message(chat_id=update.effective_chat.id, text="Invalid argument")


setmenudisplay_handler = CommandHandler('setmenudisplay', setmenudisplay)
dispatcher.add_handler(setmenudisplay_handler)


##############################

@adminonly
def setautosendmenu(update, context):
	boolean = context.args[0].lower()
	if boolean == "true" or boolean == "false":
		data["chats"][str(update.effective_chat.id)]["autoSendMenu"] = boolean
		dumpToConfigFile(data)
		context.bot.send_message(chat_id=update.effective_chat.id, text="Updated!")
	else:
		context.bot.send_message(chat_id=update.effective_chat.id, text="Invalid argument")


setautosendmenu_handler = CommandHandler('setautosendmenu', setautosendmenu)
dispatcher.add_handler(setautosendmenu_handler)


##############################


@adminonly
def setautosendmenutime(update, context):
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

	data["chats"][str(update.effective_chat.id)]["autoSendMenuTimeOfDay"] = hour + minute
	dumpToConfigFile(data)
	context.bot.send_message(chat_id=update.effective_chat.id, text=f"Auto send set to {hour}:{minute}!")


setautosendmenutime_handler = CommandHandler('setautosendmenutime', setautosendmenutime)
dispatcher.add_handler(setautosendmenutime_handler)


##############################

# this runs when the bots receives undefined commands
def echo(update, context):
	context.bot.send_message(chat_id=update.effective_chat.id, text="Invalid command")


echo_handler = MessageHandler(Filters.text, echo)
dispatcher.add_handler(echo_handler)

##############################

tl = Timeloop()


@tl.job(interval=timedelta(seconds=55))
def resetSentMenu():
	# if it's midnight, iterate over every chat and reset the menuSentToday
	if datetime.datetime.now().hour == 0 and datetime.datetime.now().minute == 0:
		for chat in data["chats"]:
			# reset the menuSentToday variable
			data["chats"][chat]["menuSentToday"] = "0"

		dumpToConfigFile(data)


@tl.job(interval=timedelta(seconds=55))
def auto_send_menu():
	# iterate over every chat
	for chat in data["chats"]:
		# we don't want to send the menu on weekends
		if datetime.datetime.now().weekday() == 5 or datetime.datetime.now().weekday() == 6:
			continue

		# if autoSendMenu == false, skip this chat
		if data["chats"][chat]["autoSendMenu"] == "false":
			continue

		# if hours don't match, continue
		if datetime.datetime.now().hour != int(data["chats"][chat]["autoSendMenuTimeOfDay"][:2]):
			continue

		# then check if the minutes matches
		if datetime.datetime.now().minute != int(data["chats"][chat]["autoSendMenuTimeOfDay"][-2:]):
			continue

		# send the menu
		bot = telegram.Bot(access_token)
		menu(chat, bot)


if __name__ == "__main__":
	updater.start_polling()
	tl.start(block=True)
