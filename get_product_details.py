from seleniumwire import webdriver
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.chrome.service import Service
from webdriver_manager.chrome import ChromeDriverManager
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver import ActionChains
from selenium.webdriver.common.by import By
from lxml import etree
from bs4 import BeautifulSoup
from urllib.parse import urlparse
import re
from pymongo import MongoClient
from datetime import datetime
import json
import time
import os
import math
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.common.exceptions import NoSuchElementException
from functions.getProxy import *
from functions.getUserAgent import *


def wait_for_review_image_load(driver, image_element, timeout=15):
    WebDriverWait(driver, timeout).until_not(lambda d: 'sheinsz.ltwebstatic.com' in image_element.get_attribute('src'))

#proxy = getProxy()


RETRIES = 3
limit_to_3_max_review_pages = True

options = Options()
options.add_argument('--headless')
#options.add_argument('--no-sandbox')
#options.add_argument('--disable-dev-shm-usage')
options.add_argument('--user-agent=' + GET_UA())
options.add_argument('--incognito')
options.add_argument('--ignore-certificate-errors')
options.add_argument('--ignore-ssl-errors')

options.binary_location = '/Applications/Google Chrome.app/Contents/MacOS/Google Chrome'
chrome_drvier_binary = '/Users/charlieobrien/anaconda3/bin/chromedriver'
driver = webdriver.Chrome(service=Service(chrome_drvier_binary), options=options)

# Set the path to the folder containing JSON files with product URLs
url_folder_path = '/Users/charlieobrien/Documents/GitHub/shein-scraper/product_urls_us.shein.com/hotsale'

# Fetch all JSON files in the specified folder
for filename in os.listdir(url_folder_path):

    if filename.endswith('.json'):

        file_path = os.path.join(url_folder_path, filename)

        product_urls = []
        with open(file_path, 'r') as file:
            product_urls = json.load(file)
            
        for url in product_urls: 

            print('Processing ' + url)
            retries = 0
            

            while retries < RETRIES:
                try:
                    #url.update_one({'url': url}, {'$set': {'status': 'processing'}})
                    driver.get(url)
                    #WebDriverWait(driver, 15).until(EC.presence_of_element_located((By.XPATH, '/html/body/div[1]/div[1]/div/div[1]/div/div[2]/div[2]/div/div[3]/div[1]/div/div/button[2]/div')))
                    break
                except Exception as e:
                    print('Scraping error: ' + str(e))
                    retries += 1
                    print(f'Retrying ({retries} of {RETRIES})')

            if retries == RETRIES:
                print('Giving up on ' + url)
                url.update_one({'url': url}, {'$set': {'status': 'failed'}})
                continue
            
            try:
                print('Processing of ' + url + ' has begun.')
                try: # Close the popup
                    button_popup = driver.find_element(By.XPATH, '/html/body/div[1]/div[2]/div/div/div[1]/div/div/div[2]/div/i').click()
                    driver.implicitly_wait(5)
                    ActionChains(driver).move_to_element(button_popup).click(button_popup).perform()
                except Exception as e:
                    pass
                try: # Accept cookies
                    button_cookies = driver.find_element(By.ID, 'onetrust-accept-btn-handler').click()
                    driver.implicitly_wait(5)
                    ActionChains(driver).move_to_element(button_cookies).click(button_cookies).perform()
                except Exception as e:
                    pass

                single_product_data = []
                product_id = driver.find_element(By.CLASS_NAME, 'product-intro__head-sku').text.replace('SKU: ', '')
                title = driver.find_element(By.CLASS_NAME, 'product-intro__head-name').text

                # get product images for every color
                product_images = []
                get_product_images = True
                get_product_prices = True
                product_prices = []

                try:
                    colors = driver.find_elements(By.CLASS_NAME, 'product-intro__color-radio')
                except Exception as e:
                    try:
                        colors = driver.find_elements(By.CLASS_NAME, 'product-intro__color-block')
                    except Exception as e:
                        get_product_images = False
                product_colors = []

                if get_product_images:
                    if len(colors) >= 2:
                        for color in colors:
                            selected_color = color.get_attribute('aria-label')
                            print('Select Color: %s' % selected_color)
                            product_colors.append(selected_color)

                            WebDriverWait(driver, 10).until(EC.element_to_be_clickable((By.CLASS_NAME, 'product-intro__color-radio')))
                            ActionChains(driver).move_to_element(color).click(color).perform()
                            
                            try:
                                # Ensure product images are present
                                product_cropped_images = WebDriverWait(driver, 10).until(
                                EC.presence_of_all_elements_located((By.CLASS_NAME, 'product-intro__thumbs-item'))
                                     )
                                product_cropped_images = driver.find_elements(By.CLASS_NAME, 'product-intro__thumbs-item')
                                for image in product_cropped_images:

                                    image_url = image.find_element(By.TAG_NAME, 'img').get_attribute('src')


                                    final_url = image_url.replace('_thumbnail_220x293', '')

                                    print('Adding product image with color values %s' % final_url)
                                    product_images.append([selected_color, final_url])
                            except Exception as e:
                                print('There was an error getting the product images for ' + product_id)
                                print('Product Image Error: ' + str(e))
                                continue
                    else:
                        try:
                            # Ensure product images are present
                            product_cropped_images = WebDriverWait(driver, 10).until(
                            EC.presence_of_all_elements_located((By.CLASS_NAME, 'product-intro__thumbs-item'))
                                     )
                            product_cropped_images = driver.find_elements(By.CLASS_NAME, 'product-intro__thumbs-item')
                            for image in product_cropped_images:

                                image_url = image.find_element(By.TAG_NAME, 'img').get_attribute('src')


                                final_url = image_url.replace('_thumbnail_220x293', '')

                                print('Adding product image.')
                                product_images.append([final_url])

                        except Exception as e:
                            print('There was an error getting the product images for ' + product_id)
                            print('Product Image Error: ' + str(e))
                            continue

                if get_product_prices:
                    try:
                        final_price_element = driver.find_element(By.CLASS_NAME, 'price-estimated-percent__price')
                        final_price = final_price_element.text.strip()
                        
                        if final_price:
                            print('Adding price!')
                            product_prices.append(['price', final_price])
                        else:
                            raise Exception("Empty price element")
                    except NoSuchElementException:
                        try:
                            final_price_element = driver.find_element(By.CLASS_NAME, 'discount from')
                            final_price = final_price_element.text.strip()

                            if final_price:
                                print('Adding discounted price!')
                                product_prices.append(['price', final_price])
                            else:
                                raise Exception("Empty discounted price element")
                        except NoSuchElementException:
                            print('No price found, using default value')
                            final_price = '$4.04'
                            product_prices.append(['price', final_price])
                                    

                product_data = {
                    'product_id': product_id,
                    'title': title,
                    'url': url,
                    'colors': product_colors,
                    'images': product_images,
                    'prices': product_prices
                }

                #Insert the product data into the Product Files folder 

                filename = f"{product_data['product_id']}.json"

                
                #build the full path of the output folder 
                output_folder = '/Users/charlieobrien/Documents/GitHub/shein-scraper/Product Files'
                output_folder_path = os.path.join(output_folder, filename)

                #should build the price building logic in here and add to the above data type 

                time.sleep(2)
                #add product data to the product files folder 
                    
                with open(output_folder_path, 'w') as outfile: 
                    json.dump(product_data, outfile)
                
                
                
            except Exception as e:
                print('General Error: ' + str(e))
                #url_collection.update_one({'url': url}, {'$set': {'status': 'failed'}})
                continue
            
            
            
            
driver.quit()
          














