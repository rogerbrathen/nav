/*
 * $Id$
 *
 * Copyright 2002-2004 Norwegian University of Science and Technology
 * 
 * This file is part of Network Administration Visualized (NAV)
 * 
 * NAV is free software; you can redistribute it and/or modify
 * it under the terms of the GNU General Public License as published by
 * the Free Software Foundation; either version 2 of the License, or
 * (at your option) any later version.
 * 
 * NAV is distributed in the hope that it will be useful,
 * but WITHOUT ANY WARRANTY; without even the implied warranty of
 * MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
 * GNU General Public License for more details.
 * 
 * You should have received a copy of the GNU General Public License
 * along with NAV; if not, write to the Free Software
 * Foundation, Inc., 59 Temple Place, Suite 330, Boston, MA  02111-1307  USA
 * 
 * Author: Kristian Eide <kreide@gmail.com>
 */

import javax.servlet.http.HttpServletRequest;


public class Input
{
	public Input(HttpServletRequest InReq, Com InCom)
	{
		req = InReq;
		com = InCom;
		h = com.getHandler();
	}

	public void begin()
	{

			String sect;

			sect = req.getParameter("section");

			if (sect != null)
			{
				if (sect.length() > 0)
				{
					html = h.handleSection(sect);
				}
			}

			if (html == null || html.equals("") )
			{
				if (com.getUser().getAuth())
				{

					html = "html/nav/main.html";

				} else
				{
					html = "html/main.html";
				}
			}


	}

	public String getHtml()
	{
		return html;
	}

	HttpServletRequest req;
	Com com;
	User u;
	Handler h;
	String html;

}
