import os
import conf
name = "werkzeug-docs-" + conf.version
os.chdir("_build")
os.rename("html", name)
os.system("tar czf %s.tar.gz %s" % (name, name))
os.rename(name, "html")
