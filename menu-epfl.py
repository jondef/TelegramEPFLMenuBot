# pip install python-telegram-bot --upgrade
from telegram.ext import Updater, CommandHandler, MessageHandler, Filters
import telegram.parsemode

# pip install pillow
from PIL import Image
from io import BytesIO
import json

# pip install selenium
from selenium.webdriver.chrome.options import Options
from selenium import webdriver

# selenium requires chromedriver:
# $ yay -S chromium // chromium browser comes included with chromedriver


try:
	with open('configggg.json') as file:
		print(file.readlines())
except IOError:
	print("File not accessible")


# put image on the poll next to the item that has an image.
# put the items on the same order as the image
# only output the menu at 12h each day.


# configure the chrome driver
chrome_options = Options()
chrome_options.add_argument("--headless")
chrome_options.add_argument("--window-size=1920x1080")
chrome_driver = "chromedriver"
driver = webdriver.Chrome(options=chrome_options, executable_path=chrome_driver)


# configure the telegram bot
try:
	with open('bot_access_token.txt', 'r') as file:
		print(f"Using token: {file.readlines()[0]}")
		access_token = file.readlines()[0]
		print(access_token)
except IOError:
	print("File not accessible")
	exit()
updater = Updater(token=access_token, use_context=True)
dispatcher = updater.dispatcher

# restaurant name
# restaurant id
Restaurants = [
	(
		"Orni",
		19,
	),
	(
		"Caféteria BC",
		18,
	),
	(
		"Le Puur",
		42,
	),
	(
		"Hollycow",
		None,
	),
	(
		"Le Parmentier",
		23,
	),
	(
		"Le Corbusier",
		22,
	),
	(
		"Roulottes",
		None,
	)

]

pollQuestion = "Where do you want to eat?"
pollOptions = [Restaurant[0] for Restaurant in Restaurants]


# does some web scraping to collect the image of the menu
def captureMenuPic(aResto_id: int):
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

	return bytesio


# with open("screenshot.png", 'rb') as file:
#    context.bot.send_photo(chat_id=update.effective_chat.id, photo=file)

# driver.get_screenshot_as_file("capture.png")
# element.screenshot("path.png")
# driver.quit()


###############################

# sends the menu pictures with the appropriate caption
def sendMenuPics(update, context):
	for restaurant in Restaurants:
		# if a picture of the menu was found
		if restaurant[1] is not None:
			context.bot.send_photo(update.effective_chat.id, captureMenuPic(restaurant[1]),
								   caption=f"{restaurant[0]}'s menu", disable_notification=False,
								   reply_to_message_id=None, reply_markup=None, timeout=20, parse_mode=None)


##############################

# configure the start command
def start(update, context):
	context.bot.send_message(chat_id=update.effective_chat.id, text="Cool! Type `/help` to get started!",
							 parse_mode=telegram.ParseMode.MARKDOWN)


start_handler = CommandHandler('start', start)
dispatcher.add_handler(start_handler)


#############################

def caps(update, context):
	text_caps = ' '.join(context.args).upper()
	context.bot.send_message(chat_id=update.effective_chat.id, text=text_caps)


caps_handler = CommandHandler('caps', caps)
dispatcher.add_handler(caps_handler)


#############################

def get_menu(update, context):
	context.bot.send_chat_action(chat_id=update.effective_chat.id, action=telegram.ChatAction.TYPING)
	context.bot.send_message(chat_id=update.effective_chat.id, text="Alright, getting today's menu...")
	sendMenuPics(update, context)
	context.bot.sendPoll(update.effective_chat.id, pollQuestion, pollOptions, disable_notification=False,
						 reply_to_message_id=None, reply_markup=None, timeout=None)


menu_handler = CommandHandler('menu', get_menu)
dispatcher.add_handler(menu_handler)


##############################

def help(update, context):
	context.bot.send_message(chat_id=update.effective_chat.id, text=
	"""
    `/help` - Print this message
    `/menu` - Get the menus with the images and poll\n
    """,
							 parse_mode=telegram.ParseMode.MARKDOWN)


help_handler = CommandHandler('help', help)
dispatcher.add_handler(help_handler)


##############################

# this runs when the bots recieves undefined commands
def echo(update, context):
	context.bot.send_message(chat_id=update.effective_chat.id, text="What?")


echo_handler = MessageHandler(Filters.text, echo)
dispatcher.add_handler(echo_handler)

##############################

updater.start_polling()
