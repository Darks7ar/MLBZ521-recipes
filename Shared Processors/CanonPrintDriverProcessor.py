#!/usr/bin/env python
#
# Copyright 2022 Zack Thompson (mlbz521)
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#     http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.

from __future__ import absolute_import, print_function

import json
import os
import sys
import time

from autopkglib import ProcessorError, URLGetter


if not os.path.exists("/Library/AutoPkg/Selenium"):
    raise ProcessorError("Selenium is required for this recipe!  "
    "Please review my Shared Processors README.")

from SeluniumWebScrapper import WebEngine

sys.path.insert(0, "/Library/AutoPkg/Selenium")
from selenium.webdriver.support.ui import Select, WebDriverWait
from selenium.webdriver.support.expected_conditions import presence_of_element_located


__all__ = ["CanonPrintDriverProcessor"]


class CanonPrintDriverProcessor(URLGetter):
    """This processor finds the download URL for the "recommended" Canon print driver.
    """

    input_variables = {
        # "support_url": {
        #     "required": False,
        #     "description": (
        #         "The URL to the Canon product support page.",
        #         "Default:  https://www.usa.canon.com/internet/portal/us/home/support"
        #     )
        # },
        "model": {
            "required": True,
            "description": (
                "The official model name of the Canon Printer to search for."
            )
        },
        "os_version": {
            "required": False,
            "description": (
                "The OS version to search against.",
                "Default:  'MACOS_11_0' (i.e. Big Sur)"
            )
        },
        "web_driver": {
            "required": False,
            "description": (
                "The web driver engine to use.  Only Chrome is supported at this time, "
                "but support for additional web drivers can be added.",
                "Default:  Chrome"
            )
        },
        "web_driver_path": {
            "required": False,
            "description": (
                "The path to the web driver.  _If_ it is not in your system $PATH.",
                "Default:  $PATH"
            )
        },
        "web_driver_binary_location": {
            "required": False,
            "description": (
                "The path to the browser's binary.  Defaults to using Chromium.",
                "Default:  /Applications/Chromium.app/Contents/MacOS/Chromium"
            )
        }
    }
    output_variables = {
        "url": {
            "description": "Returns the url to download."
        }
    }

    description = __doc__


    def canon_product_parse(self, node, model):
        """Parse the Canon Product JSON Content for the provided model.

        Args:
            node (dict): a dict of the Canon Product JSON Content
            model (str): the "official" name of a printer model

        Returns:
            str: A url to the printer models web page
        """

        for key, item in node.items():

            if type(item) is dict:
                self.canon_product_parse(item, model)

            elif type(item) is list:

                for printer in item:
                    self.canon_product_parse(printer, model)

            elif item == model:
                self.link = node.get("spdplinks")


    def main(self):
        """Do the main thing."""

        # Define variables
        model = self.env.get("model")
        url_products_list = self.env.get("url_products_list")
        # support_url = self.env.get(
            # "support_url", "https://www.usa.canon.com/internet/portal/us/home/support")
        os_version = self.env.get("os_version", "MACOS_11_0")
        web_driver = self.env.get("web_driver", "Chrome")
        web_driver_path = self.env.get("web_driver_path")
        web_driver_binary_location = self.env.get("web_driver_binary_location")
        recipe_cache_dir = self.env.get("RECIPE_CACHE_DIR")
        json_product_list = f"{recipe_cache_dir}/product_list.json"

        self.output(f"Searching for printer model:  {model}", verbose_level=1)
        self.output(f"Canon's json product list URL:  {url_products_list}", verbose_level=2)

        if not os.path.exists(recipe_cache_dir):
            raise ProcessorError("Recipe Cache directory does not exist!")

        # Build the required curl switches
        curl_opts = [
            "--url", url_products_list,
            "--request", "GET",
            "--output", json_product_list
        ]
        headers = {'Accept': 'application/json'}

        try:
            # Initialize the curl_cmd, add the curl options, and execute curl
            curl_cmd = self.prepare_curl_cmd()
            self.add_curl_headers(curl_cmd, headers)
            curl_cmd.extend(curl_opts)
            result = self.download_with_curl(curl_cmd)

        except:
            raise ProcessorError(f"Failed to match the provided model:  {model}")

        try:
            # Load the JSON Response
            with open(json_product_list, 'rb') as json_product_list_file:
                json_data = json.load(json_product_list_file)

            self.canon_product_parse(json_data, model)
            self.output(f"Model downloads page:  {self.link}", verbose_level=2)

        except:
            raise ProcessorError("Failed to find a model url in the results!")

        with WebEngine(
            web_driver, web_driver_binary_location, path=web_driver_path,) as web_engine:

            try:
                web_engine.get(self.link)

            except:
                raise ProcessorError("Failed to access the model page.")

            try:
                # Open the "Drivers & Download" section
                WebDriverWait(web_engine, timeout=10).until(
                    lambda d: d.find_element_by_class_name("drivers_downloads_tab")
                )
                web_engine.find_element_by_class_name("drivers_downloads_tab").click()

            except:
                raise ProcessorError("Failed to find and open the \"Drivers & Downloads\" section.")

            try:
                # Select the desired OS Version
                WebDriverWait(web_engine, timeout=10).until(
                    lambda d: d.find_element_by_id("dd_platform")
                )
                time.sleep(1)
                select_os = Select(web_engine.find_element_by_id("dd_platform"))
                presence_of_element_located(select_os)
                select_os.select_by_value(os_version)

            except:
                raise ProcessorError("Failed to select the desired OS Version")

            try:
                # Find the "Recommended Driver(s)" section
                drivers_section = web_engine.find_element_by_id("DataTables_Table_2")

            except:
                raise ProcessorError("Failed to find the \"Recommended Driver(s)\" section.")

            try:
                # Click the "SELECT" button so the download link becomes visible
                drivers_section.find_element_by_xpath("//*/tbody/tr/td[*]/button").click()

            except:
                raise ProcessorError(
                    "Failed to find and click the SELECT button for the recommended driver.")

            try:
                # Get the hyperlink for the driver download file
                download_url = drivers_section.find_element_by_xpath(
                    "//*/tbody/tr[*]/td/table/tbody/tr[*]/td[*]/div/div/a").get_attribute("href"
                )

            except:
                raise ProcessorError(
                    "Failed to find and collect the download url from the download button.")

        if not download_url:
            raise ProcessorError("Failed to find a matching download type for the provided model.")

        # Return results
        self.env["url"] = download_url
        self.output(f'Download URL: {self.env["url"]}', verbose_level=1)


if __name__ == "__main__":
    processor = CanonPrintDriverProcessor()
    processor.execute_shell()
