import importlib


def main():
    package_manager = importlib.import_module("argostranslate.package")
    translator = importlib.import_module("argostranslate.translate")

    installed_codes = {
        language.code for language in translator.get_installed_languages()
    }
    if "en" not in installed_codes or "zh" not in installed_codes:
        print("正在获取 Argos 英中离线模型列表……")
        package_manager.update_package_index()
        available_packages = package_manager.get_available_packages()
        packages = [
            package for package in available_packages
            if package.from_code == "en" and package.to_code == "zh"
        ]
        if not packages:
            raise RuntimeError("Argos 模型仓库中没有找到 English → Chinese 语言包。")

        selected_package = packages[0]
        print(
            f"正在下载英中离线模型（{selected_package.from_name} → "
            f"{selected_package.to_name}），文件较大，请耐心等待……"
        )
        package_manager.install_from_path(selected_package.download())

    installed_codes = {
        language.code for language in translator.get_installed_languages()
    }
    if "en" not in installed_codes or "zh" not in installed_codes:
        raise RuntimeError("安装后仍未找到 English → Chinese 离线语言模型。")

    sample = translator.translate("Open source software", "en", "zh")
    if not sample.strip():
        raise RuntimeError("离线模型测试失败：翻译结果为空。")
    print(f"离线翻译已安装并通过测试：Open source software → {sample}")


if __name__ == "__main__":
    main()
