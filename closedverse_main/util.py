from lxml import html
# Todo: move all requests to using requests instead of urllib3
import urllib.request, urllib.error
import requests
from lxml import etree
from random import choice
import json
import time
import os.path
from PIL import Image, ExifTags, ImageFile
from datetime import datetime
from binascii import crc32
from math import floor
from hashlib import md5, sha1
# lol bye Cloudinary, see you another day
#import cloudinary
#import cloudinary.uploader
#import cloudinary.api
import io
from uuid import uuid4
import imghdr
import base64
from closedverse import settings
import re
from os import remove, rename

def HumanTime(date, full=False):
	now = time.time()
	if ((now - date) >= 345600) or full:
		return datetime.fromtimestamp(date).strftime('%m/%d/%Y %I:%M %p')
	interval = (now - date) or 1
	if interval <= 59:
		return 'Less than a minute ago'
	intvals = [86400, 3600, 60, ]
	for i in intvals:
		if interval < i:
			continue
		nounits = floor(interval / i)
		text = {86400: 'day', 3600: 'hour', 60: 'minute', }.get(i)
		if nounits > 1:
			text += 's'
		return str(nounits) + ' ' + text + ' ago';


def get_mii(id):
	# Using Miiverse off-device server, doesn't work after Miiverse shutdown
	"""
	try:
		page = urllib.request.urlopen('https://miiverse.nintendo.net/users/{0}/favorites'.format(id)).read()
	except urllib.error.HTTPError:
		return False
	ftree = html.fromstring(page)
	miihash = ftree.xpath('//*[@id="sidebar-profile-body"]/div/a/img/@src')[0].split('.net/')[1].split('_n')[0]
	screenname = ftree.xpath('//*[@id="sidebar-profile-body"]/a/text()')[0]
	ou_check = ftree.xpath('//*[@id="sidebar-profile-body"]/div/@class')
	if ou_check and 'official-user' in ou_check[0]:
		return False
	if "img/anonymous-mii.png" in miihash:
		miihash = ''
	"""
	nnid = requests.get('https://pf2m.com/mii/' + id)
	if nnid.status_code == 404:
		return False
	nnid.raise_for_status()
	repre = nnid.json()

	nnid = repre['user_id']
	miihash = repre['images'][0]['url'].split('.net/')[1].split('_')[0]
	print(miihash)
	screenname = repre['name']

	# Also todo: Return the NNID based on what accountws returns, not the user's input!!!
	return [miihash, screenname, nnid]


def recaptcha_verify(request, key):
	if not request.POST.get('g-recaptcha-response'):
		return False
	re_request = urllib.request.urlopen('https://www.google.com/recaptcha/api/siteverify?secret={0}&response={1}'.format(key, request.POST['g-recaptcha-response']))
	jsond = json.loads(re_request.read().decode())
	if not jsond['success']:
		return False
	return True

ImageFile.LOAD_TRUNCATED_IMAGES = True
def image_upload(img, stream=False, drawing=False):
	if stream:
		decodedimg = img.read()
	else:
		# Brand New drawing checksum
		# Never mind
		#if drawing:
		#	if not '----/' in img:
		#		return 1
		#	hasha = img.split('----/')
			# Appears to be broken; works some of the time, other times
			#if not 0 > int(hasha[0]) and crc32(bytes(hasha[1], 'utf-8')) != int(hasha[0]):
			#	return 1
		#	img = hasha[1]
		try:
			decodedimg = base64.b64decode(img)
		except ValueError:
			return 1
	if stream:
		if not 'image' in img.content_type:
			return 1
		if 'audio' in img.content_type or 'video' in img.content_type:
			return 1
	# upload svg?
	#if 'svg' in mime:
	#
	try:
		im = Image.open(io.BytesIO(decodedimg))
	# OSError is probably from invalid images, SyntaxError probably from unsupported images
	except (OSError, SyntaxError):
		return 1
	# Taken from https://coderwall.com/p/nax6gg/fix-jpeg-s-unexpectedly-rotating-when-saved-with-pil
	if hasattr(im, '_getexif'):
		orientation = 0x0112
		exif = im._getexif()
		if exif is not None:
			orientation = exif.get(orientation)
			rotations = {
				3: Image.ROTATE_180,
				6: Image.ROTATE_270,
				8: Image.ROTATE_90
			}
			if orientation in rotations:
				im = im.transpose(rotations[orientation])
	im.thumbnail((1280, 1280), Image.ANTIALIAS)

	# Let's check the aspect ratio and see if it's crazy
	# IF this is a drawing
	if drawing and ((im.size[0] / im.size[1]) < 0.30):
		return 1

	# I know some people have aneurysms when they see people actually using SHA1 in the real world, for anything in general.
	# Yes, we are really using it. Sorry if that offends you. It's just fast and I don't feel I need anything more random, since we are talking about IMAGES.
	imhash = sha1(im.tobytes()).hexdigest()
	# File saving target
	target = 'png'
	if stream:
	# If we have a stream and either a JPEG or a WEBP, save them as those since those are a bit better than plain PNG
		if 'jpeg' in img.content_type:
			target = 'jpeg'
			im = im.convert('RGB')
		elif 'webp' in img.content_type:
			target = 'webp'
	floc = imhash + '.' + target
	# If the file exists, just use it, that's what hashes are for.
	if not os.path.exists(settings.MEDIA_ROOT + floc):
		im.save(settings.MEDIA_ROOT + floc, target, optimize=True)
	return settings.MEDIA_URL + floc

# Todo: Put this into post/comment delete thingy method
def image_rm(image_url):
	if settings.image_delete_opt:
		if settings.MEDIA_URL in image_url:
			sysfile = image_url.split(settings.MEDIA_URL)[1]
			sysloc = settings.MEDIA_ROOT + sysfile
			if settings.image_delete_opt > 1:
				try:
					remove(sysloc)
				except:
					return False
				else:
					return True
			# The RM'd directory to move it to
			rmloc = sysloc.replace(settings.MEDIA_ROOT, settings.MEDIA_ROOT + 'rm/')
			try:
				rename(sysloc, rmloc)
			except:
				return False
			else:
				return True
		else:
			return False

def get_gravatar(email):
	try:
		page = urllib.request.urlopen('https://gravatar.com/avatar/'+ md5(email.encode('utf-8').lower()).hexdigest() +'?d=404&s=128')
	except:
		return False
	return page.geturl()

def filterchars(str=""):
	# If string is blank, None, any other object, etc, make it whitespace so it's detected by isspace.
	if not str:
		str = " "
	# Forbid chars in this list, currently: Right-left override, largest Unicode character.
	# Now restricting everything in https://www.reddit.com/r/Unicode/comments/5qa7e7/widestlongest_unicode_characters_list/
	forbid = ["\u202e", "\ufdfd", "\u01c4", "\u0601", "\u2031", "\u0bb9", "\u0bf8", "\u0bf5", "\ua9c4", "\u102a", "\ua9c5", "\u2e3b", "\ud808", "\ude19", "\ud809", "\udc2b", "\ud808", "\udf04", "\ud808", "\ude1f", "\ud808", "\udf7c", "\ud808", "\udc4e", "\ud808", "\udc31", "\ud808", "\udf27", "\ud808", "\udd43", "\ud808", "\ude13", "\ud808", "\udf59", "\ud808", "\ude8e", "\ud808", "\udd21", "\ud808", "\udd4c", "\ud808", "\udc4f", "\ud808", "\udc30", "\ud809", "\udc2a", "\ud809", "\udc29", "\ud808", "\ude19", "\ud809", "\udc2b"]
	for char in forbid:
		if char in str:
			str = str.replace(char, " ")
	if str.isspace():
		try:
			girls = json.load(open(settings.BASE_DIR + '/girls.json'))
		except:
			girls = ['None']
		return choice(girls)
	return str

""" Not using getipintel anymore
def getipintel(addr):
	# My router's IP prefix is 192.168.1.*, so this works in debug
	if settings.ipintel_email and not '192.168' in addr:
		try:
			site = urllib.request.urlopen('https://check.getipintel.net/check.php?ip={0}&contact={1}&flags=f'
			.format(addr, settings.ipintel_email))
		except:
			return 0
		return float(site.read().decode())
	else:
		return 0
"""
# Now using iphub
def iphub(addr):
	if settings.iphub_key and not '192.168' in addr:
		get = requests.get('http://v2.api.iphub.info/ip/' + addr, headers={'X-Key': settings.iphub_key})
		if get.json()['block'] == 1:
			return True
		else:
			return False

# NNID blacklist check
def nnid_blacked(nnid):
	blacklist = json.load(open(settings.nnid_forbiddens))
	# The NNID server omits dashes and dots from NNIDs, gotta make sure nobody gets through this
	nnid = nnid.lower().replace('-', '').replace('.', '')
	if nnid in blacklist:
		return True
	return False
